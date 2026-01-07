#import "@preview/bloated-neurips:0.7.0": botrule, midrule, toprule

\
= Data Acquisition and Engineering


To address the scarcity of public datasets for Counter-Strike 2 (CS2) match prediction, we engineered a custom data acquisition pipeline. While datasets for Counter-Strike: Global Offensive (CS:GO) exist @csgodataset, the transition to the Source 2 engine rendered previous data obsolete for mechanical and physics-based prediction models @source2. Consequently, we targeted #link("https://hltv.org")[HLTV], the premier repository for CS2 esports data, to construct a novel dataset comprising over 20,000 professional matches @hltv.

== Adversarial Scraping and WAF Evasion

The primary challenge in acquiring data from HLTV is the implementation of a strict Cloudflare Web Application Firewall (WAF), which actively fingerprints and blocks conventional scraping tools @cfwaf. Standard headless browser implementations (vanilla Puppeteer or Selenium) are trivial for WAFs to detect due to distinct TLS fingerprints (JA3/JA4 signatures) and the absence of rendering stacks (WebGL, Canvas) @laperdrix2020survey @vastel2020fpcrawlers

To circumvent this, we employed a *headful* browser instrumentation strategy using `patchright`, a modified fork of Playwright designed to mask automation signals @github_patchright. This approach simulates a legitimate user agent with a complete rendering pipeline. However, deploying headful browsers in a headless containerized environment necessitates display emulation @zhou2016dockerxvfb. We utilized `Xvfb` (X virtual framebuffer) @xvfb to create a virtual display buffer in memory, allowing the browser to render graphical elements without physical hardware.

=== Containerization and Debug Protocol Bridging

A critical hurdle in containerizing this architecture was the Chrome DevTools Protocol (CDP) restriction. By default, Chrome binds the CDP to `localhost`, preventing external scrapers or orchestrators within a distributed mesh from attaching to the browser instance. We resolved this by utilizing `socat` to proxy TCP traffic from an exposed container port to the internal loopback interface of the browser.

The following entrypoint script demonstrates the orchestration of the display server, the port forwarding proxy, and the browser process:

#figure(
  caption: [Container entrypoint script for headful browser emulation.],
  kind: "code",
  supplement: "Listing",
  ```bash
  #!/bin/bash
  set -e

  # Clean up any stale X server lock files
  rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

  # Start Xvfb in the background: Emulating 1920x1080 resolution
  export DISPLAY=:99
  Xvfb :99 -screen 0 1920x1080x24 &
  XVFB_PID=$!

  # Wait for X server initialization
  sleep 2

  # Configure Chrome to bind CDP to internal port 9223
  export CHROME_REMOTE_DEBUG_PORT="9223"

  # Proxy external request from 9222 to internal 127.0.0.1:9223 via socat
  echo "Starting socat proxy from port 9222 to 127.0.0.1:9223..."
  socat TCP-LISTEN:9222,fork,reuseaddr TCP:127.0.0.1:9223 &
  SOCAT_PID=$!

  # Initialize the browser automation wrapper
  /app/.venv/bin/browser &
  BROWSER_PID=$!

  # Graceful shutdown handler
  trap "kill $BROWSER_PID $SOCAT_PID $XVFB_PID 2>/dev/null; exit" SIGTERM SIGINT

  wait $BROWSER_PID
  rm -rf /tmp/.X99-lock
  ```,
)

== Distributed Orchestration Strategy

To achieve the throughput required to scrape nearly three years of historical data, we implemented a distributed task queue using *Celery* backed by *Redis*. Redis serves as both the message broker and the distributed locking mechanism to ensure atomic operations on specific match IDs.

While we evaluated modern workflow orchestrators like *Prefect* and *Apache Airflow*, we determined that their architectural overhead was disproportionate to the granularity of our workload. Our scraping strategy relies on high-concurrency, short-lived tasks (micro-batches) rather than long-running, interdependent workflows.

=== The Orchestrator Overhead Problem
Workflow engines like Airflow utilize a "Scheduler Loop" architecture. This component continuously parses DAG (Directed Acyclic Graph) files and commits state transitions to a metadata database before a task can even be queued. As noted by #cite(label("harenslak2021airflow"), form: "prose"), this design introduces a measurable "scheduler heartbeat" latency—often ranging from hundreds of milliseconds to seconds—which creates a bottleneck when dispatching thousands of sub-second scraping events.

=== The Task Queue Advantage
In contrast, Celery operates as a pure distributed task queue. It bypasses the DAG parsing and state-persistence loops entirely, allowing workers to consume messages directly from the Redis broker with near-zero latency. Recent studies in high-throughput engineering workflows have demonstrated that decoupling task execution from complex orchestration state significantly improves scalability for atomic, parallelizable workloads @kleppmann2017designing.

By selecting Celery, we maintained a steady ingestion rate of ~3.5 seconds per match, effectively trading the observability features of an orchestrator for the raw throughput of a message queue.


#figure(
  caption: [Comparative analysis of orchestration tools for high-throughput scraping workloads.],
  table(
    columns: (auto, 1fr, 1fr, 1fr),
    align: left + horizon,
    stroke: none,
    toprule,
    table.header([Feature], [Celery], [Apache Airflow], [Prefect]),
    midrule, [Primary Paradigm], [Distributed Task Queue], [Workflow Orchestration (DAGs)],
    [Modern Dataflow Orchestration],

    [State Management],
    [Transient (In-Memory/Redis)],
    [Persistent (RDBMS Writes per State)],
    [Hybrid (API/Server managed)],

    [Scheduling Latency], [Real-time (10ms)], [High (Scheduler Heartbeat >1s)], [Medium (API Polling/Push)],

    [Task Granularity], [Micro-tasks (Functions)], [Macro-tasks (Container/Job)], [Flexible (Flows & Tasks)],

    [Overhead Suitability],
    [*Optimal* for 20k+ atomic units],
    [High Overhead (DAG Parsing)],
    [Moderate Overhead (State Sync)],

    botrule,
  ),
)

=== Context Lifecycle Management

We observed that continuously reusing a single browser context led to performance degradation over time due to cookie accumulation, cache bloat, and increasing memory pressure. Conversely, instantiating a new context for every request incurs a significant overhead from repeated TLS handshakes and browser startup routines.

To balance these constraints, we engineered an asynchronous `PagePool` abstraction that manages the lifecycle of browser tabs within a persistent `patchright` context. The operational logic, illustrated in @fig-browser-page-pool-lifecycle, implements a hybrid strategy of *lazy instantiation* and *elastic recycling*:

+ *Acquisition (Phase 1):* The pool utilizes an `asyncio.Queue` for non-blocking resource distribution. When a worker requests a page, the pool first attempts to retrieve an idle instance from the queue. If the queue is depleted and the current page count is below the `max_concurrent_pages` limit, the pool lazily instantiates a new page. This ensures resources are allocated only on demand rather than pre-provisioned.

+ *Sanitization (Phase 3):* To mitigate the "dirty state" problem inherent in stateful scraping, pages are not immediately returned to the queue after use. Instead, they undergo a "soft reset" by navigating to `about:blank`. This purges the DOM and immediate JavaScript heap without destroying the underlying heavy OS process or the parent browser context.

+ *Elastic Scaling:* The release phase also enforces a `minimum_page_size` threshold. If the pool holds surplus idle pages (e.g., after a burst of short-lived tasks), the excess pages are terminated (closed) rather than recycled. This allows the memory footprint to contract dynamically during periods of lower throughput.

This architecture reduced the average end-to-end processing time—including DOM parsing and PostgreSQL I/O—to approximately 3.5 seconds per match, while maintaining long-running stability over the 20,000+ match scraping campaign.


#figure(
  image("diagrams/browser-page-pool-sequence.png"),
  caption: [Browser page pool sequence diagram],
) <fig-browser-page-pool-lifecycle>

// sequenceDiagram
//     autonumber
//     participant Worker as Worker Task
//     participant Pool as PagePool
//     participant Queue as asyncio.Queue
//     participant Browser as BrowserContext
//     participant Page as Patchright Page

//     Note over Worker, Pool: Phase 1: Acquire Page
//     Worker->>Pool: get_page() (Async Context Manager)
//     activate Pool
//     Pool->>Pool: acquire()

//     Pool->>Queue: Check qsize()

//     alt Queue Empty AND Current < Max Pages
//         Note right of Pool: Scale Up: Pool is empty but has capacity
//         Pool->>Browser: new_page()
//         activate Browser
//         Browser-->>Page: Create Instance
//         activate Page
//         Browser-->>Pool: Return Page
//         deactivate Browser
//         Pool-->>Pool: Increment current_page_count

//     else Queue Has Pages OR Max Capacity Reached
//         Note right of Pool: Reuse/Wait: Get from queue (waits if empty)
//         Pool->>Queue: await get()
//         activate Queue
//         Queue-->>Pool: Return Existing Page
//         deactivate Queue
//     end

//     Pool-->>Worker: Yield Page
//     deactivate Pool

//     Note over Worker, Page: Phase 2: Scraping Work
//     Worker->>Page: goto(url), content(), etc.
//     activate Worker
//     Worker-->>Worker: Perform business logic
//     deactivate Worker

//     Note over Worker, Pool: Phase 3: Release & Cleanup
//     Worker->>Pool: release(Page)
//     activate Pool

//     Pool->>Queue: Check qsize() vs minimum_page_size

//     alt Pool Size >= Minimum Size
//         Note right of Pool: Scale Down: Surplus pages detected
//         Pool->>Page: close()
//         deactivate Page
//         Pool-->>Pool: Decrement current_page_count

//     else Pool Size < Minimum Size
//         Note right of Pool: Recycle: Keep page for next task
//         Pool->>Page: goto("about:blank")
//         Pool->>Queue: put(Page)
//     end

//     Pool-->>Worker: Context Exit
//     deactivate Pool

=== Architecture

The architecture prioritizes stealth over raw speed by mimicking a full desktop environment. While the decoupling of logic and rendering introduces network overhead via the CDP transport layer, it provides the necessary isolation to handle the instability of headful browsers, ensuring that a browser crash does not terminate the scraping logic.


#figure(
  image("diagrams/scraping-arch.png"),
  caption: [Distributed scraping architecture leveraging headful browser emulation, containerization, and task orchestration.],
) <fig-scraping-architecture>

// flowchart TB
//     %%{ init: { "htmlLabels": false, "flowchart": { "htmlLabels": false } } }%%
//     %% Styles for different component types
//     classDef storage fill:#fffbe6,stroke:#ffd54f,stroke-width:2px,color:#000;
//     classDef container fill:#e8f5e9,stroke:#81c784,stroke-width:2px,stroke-dasharray: 2 2,color:#666;
//     classDef activeContainer fill:#ffffff,stroke-width:2px,stroke-dasharray: 0,color:#000;
//     classDef process fill:#e3f2fd,stroke:#2196f3,stroke-width:1px,color:#000;
//     classDef external fill:#fbe9e7,stroke:#ff7043,stroke-width:2px,color:#000;

//     subgraph Orchestration [Orchestration Layer]
//         Celery[Celery Scheduler]:::process
//         Redis[(Redis Broker/Locks)]:::storage
//         Celery -->|Push Scraping Task| Redis
//     end

//     subgraph WorkerPool [Distributed Worker Container Pool]
//         style WorkerPool fill:#e0f7fa,stroke:#00bcd4,stroke-width:2px,stroke-dasharray: 5 5
//         direction BT %% Stack bottom-to-top so active is in front

//         %% Representation of other pool members
//         W_N2[Worker Container N+1]:::container
//         W_N1[Worker Container N]:::container

//         subgraph WorkerContainer [Active Worker Node Container]
//             style WorkerContainer stroke:#00bcd4
//             class WorkerContainer activeContainer

//             WorkerProcess[Worker Process]:::process

//             subgraph ContextManager [Logic Layer]
//                 style ContextManager fill:#eeeeee,stroke:none
//                 NOTE_C[Manages Persistent Browser Context & Page Pool Recycling]
//             end

//             Redis -->|Pop Task / Acquire Lock| WorkerProcess
//             WorkerProcess --> ContextManager
//         end

//         %% Invisible links for stacking layout
//         W_N2 ~~~ W_N1 ~~~ WorkerContainer
//     end

//     subgraph BrowserPool [Headful Browser Container Pool]
//         style BrowserPool fill:#f1f8e9,stroke:#8bc34a,stroke-width:2px,stroke-dasharray: 5 5
//         direction BT %% Stack bottom-to-top so active is in front

//         %% Representation of other pool members
//         B_N2[Browser Container N+1]:::container
//         B_N1[Browser Container N]:::container

//         subgraph BrowserContainer [Active Browser Node Container]
//             style BrowserContainer stroke:#8bc34a
//             class BrowserContainer activeContainer
//             direction TB

//             Socat([Socat Proxy Listener :9222]):::process
//             Patchright[Patchright Browser Process CDP :9223]:::process
//             Xvfb[Xvfb Virtual Display :99]:::process

//             Socat -->|Forward Internal CDP Traffic| Patchright
//             Patchright -->|Render Graphics| Xvfb
//         end

//         %% Invisible links for stacking layout
//         B_N2 ~~~ B_N1 ~~~ BrowserContainer
//     end

//     %% Connection between Worker and Browser Nodes
//     WorkerProcess ==>|TCP Request CDP :9222| Socat
//     Socat -.->|DOM Data Response| WorkerProcess

//     subgraph Internet [External Network]
//         WAF{Cloudflare WAF}:::external
//         HLTV[HLTV.org Origin]:::external
//     end

//     %% Browser scraping flow
//     Patchright ==>|TLS Headful Request| WAF
//     WAF ==>|Validated Traffic| HLTV
//     HLTV -.->|HTML Response| WAF
//     WAF -.->|Response| Patchright

//     subgraph Persistence [Data Persistence]
//         Postgres[(PostgreSQL Cluster)]:::storage
//     end

//     %% Final data save flow
//     WorkerProcess -->|Save Parsed Data| Postgres


=== Data Schema and Volume

Data persistence is handled by a PostgreSQL database normalized to third normal form (3NF). The schema, managed via migration scripts, captures granular details including map vetoes (pick/ban phases) and player statistics.

#figure(
  image("diagrams/db-er-diagram.png"),
  caption: [Entity-Relationship diagram of the PostgreSQL database schema capturing granular match, event, map, and player statistics.],
) <fig-erdiagram>

// erDiagram
//     %% Core Entities
//     EVENTS {
//         int event_id PK
//         varchar name
//         timestamp start_date
//         timestamp end_date
//         decimal total_prize_pool
//         varchar location
//         varchar event_type
//     }

//     TEAMS {
//         int team_id PK
//         varchar name
//     }

//     PLAYERS {
//         int player_id PK
//         varchar name
//     }

//     %% Match Data
//     MATCHES {
//         int match_id PK
//         int event_id FK
//         timestamp match_date
//         int team_1_id FK
//         int team_2_id FK
//         int team_winner_id FK
//         int team_1_map_score
//         int team_2_map_score
//     }

//     VETOS {
//         int match_id PK, FK
//         int best_of
//         varchar t1_removed_1
//         varchar t1_picked_1
//         varchar left_over_map
//     }

//     %% Granular Stats
//     MAP_STATS {
//         int map_stat_id PK
//         int match_id FK
//         varchar map_name
//         int team_1_score
//         int team_2_score
//         varchar picked_by
//     }

//     PLAYER_MAP_STATS {
//         int map_stat_id PK, FK
//         int player_id PK, FK
//         int team_id FK
//         int kills_ct
//         int deaths_ct
//         decimal adr_ct
//         decimal rating_3_dot_0_ct
//         int kills_tr
//         decimal rating_3_dot_0_tr
//     }

//     %% Relationships
//     EVENTS ||--|{ MATCHES : "hosts"

//     TEAMS ||--|{ MATCHES : "plays as team 1"
//     TEAMS ||--|{ MATCHES : "plays as team 2"
//     TEAMS ||--|{ MATCHES : "wins"

//     MATCHES ||--|| VETOS : "has ban phase"
//     MATCHES ||--|{ MAP_STATS : "consists of"

//     MAP_STATS ||--|{ PLAYER_MAP_STATS : "records"
//     PLAYERS ||--|{ PLAYER_MAP_STATS : "achieves"
//     TEAMS ||--|{ PLAYER_MAP_STATS : "represented by"



== Exploratory Data Analysis

To validate the integrity and coverage of the scraped dataset, we performed a comprehensive exploratory analysis on the relational entities: Events, Matches, Map Statistics, and Player Performance. The dataset spans a temporal range from *October 4, 2023, to December 28, 2025*, capturing the complete competitive lifecycle of Counter-Strike 2 to date.

=== Dataset Volumetrics and Demographics

The scraping pipeline successfully ingested *20,309 unique matches* across *1,378 distinct events*. This corresponds to a high-density capture of the professional ecosystem, categorized into two primary tiers based on team ranking:

- *Top-Tier Events:* Approximately 30.6% of the dataset comprises events featuring "Top 50" teams, representing the elite tier of competition.
- *Grassroots & Qualifiers:* The remaining ~69.4% covers lower-tier cups and qualifiers, providing a crucial training ground for model generalization against high-variance gameplay.

#figure(
  caption: [Summary statistics of the ingested CS2 dataset.],
  table(
    columns: (1fr, 1fr),
    align: left + horizon,
    stroke: none,
    toprule,
    table.header([Entity], [Count]),

    midrule, [Matches],
    [20,309], [Events],
    [1,378], [Map Stats (Distinct Maps)],
    [43,342], [Player Map Stats],
    [430,689], [Unique Players],
    [4,998], [Unique Teams],
    [1,529], botrule,
  ),
) <tab-dataset-stats>

=== Match and Map Distributions

The distribution of match outcomes reveals a slight seeding bias. In both top-tier and non-top-tier events, `team_1` (typically the higher seed or bracket favorite) retains a win rate of approximately *55.3% to 55.9%*. This baseline probability serves as a critical prior for our predictive models.

The granular `map_stats` table reveals that the dataset contains *43,342 map iterations*. The scoring distribution follows the standard MR12 (Max Rounds 12) format introduced in CS2, though historical MR15 data may exist in the tail. The `vetos` analysis confirms a bimodal distribution in series formats, dominated by Best-of-1 (BO1) and Best-of-3 (BO3) configurations, with Best-of-5 (BO5) finals appearing as sparse outliers.

#figure(
  image("images/best_of_distribution.png"),
  caption: [Distribution of match outcomes by team seeding and series format.],
) <fig-best-of-distribution>

The map pool analysis indicates a diverse selection of competitive maps, with traditional staples like *Ancient*, *Mirage*, and *Inferno* dominating pick rates.

#figure(
  image("images/map_picks_by_best_of.png"),
  caption: [Pick rates of competitive maps in the CS2 dataset.],
) <fig-map-pick-rates>

=== Player Performance Feature Space

The deepest level of granularity resides in the `player_map_stats` relation (N=430,689). Unlike traditional box-score datasets, our feature space includes advanced economy and utility metrics specific to the Source 2 engine:

- *Rating 3.0*: A custom aggregate performance metric (`rating_3_dot_0_ct`, `rating_3_dot_0_tr`) normalized for the new MR12 economy.
- *Impact Metrics*: Granular tracking of `opening_kills`, `traded_deaths`, and `clutches` per side (CT/T).
- *Utility & Support*: Features such as `flash_assists` and `kast` (Kill, Assist, Survive, Trade) percentage, essential for quantifying non-fragging contributions.

== Feature Engineering

Transforming raw player-level statistics into predictive team-level features requires careful aggregation strategies. Since CS2 is inherently asymmetric, with Counter-Terrorist (CT) and Terrorist (TR) sides exhibiting distinct tactical constraints, we first unify side-specific metrics before applying distributional aggregations.

=== Side-Agnostic Performance Metrics

Player statistics in the `player_map_stats` table are recorded separately for CT and TR sides (e.g., `kills_ct`, `kills_tr`). To produce map-level player profiles, we sum corresponding side metrics:

$ "kills" = "kills"_"CT" + "kills"_"TR" $

This transformation is applied to all 14 core performance indicators: `kills`, `clutches`, `headshot`, `flash`, `assist`, `deaths`, `traded_deaths`, `adr`, `swing`, `rating_3_dot_0`, `opening_kills`, `opening_deaths`, `multikills`, and `kast`.

=== Team-Level Statistical Aggregation

Given the five-player composition of CS2 teams, we characterize team performance distributions using five robust statistics per metric:

1. *Mean* ($mu$): Central tendency of team skill
2. *Median* ($tilde(mu)$): Robust measure resistant to outliers (e.g., carry players)
3. *25th Percentile* ($P_(25)$): Lower-bound performance floor
4. *75th Percentile* ($P_(75)$): Upper-bound performance ceiling
5. *Standard Deviation* ($sigma$): Intra-team consistency measure

For each of the 14 performance metrics, this produces 5 aggregated features, yielding $14 times 5 = 70$ team-level descriptors per match side. Since matches involve two teams, the final feature space contains $70 times 2 = 140$ team performance features, prefixed as `t1_*` and `t2_*`.

The use of quantiles ($P_(25)$, $P_(75)$) captures the *depth* of a roster, i.e., teams with narrow interquartile ranges exhibit balanced lineups, while wide ranges indicate reliance on star players.

=== Dynamic Match Weighting via Event Context

Not all matches carry equal predictive value. A group-stage match between lower-ranked teams in an open qualifier provides weaker signal than a playoff match at a Major championship. To encode this informativeness gradient, we designed a composite weighting function that incorporates four contextual dimensions:

==== 1. Temporal Recency Decay
\
\
\

Recent matches better reflect current team form. We apply exponential decay with a half-life of 180 days:

$ w_"recency" = 0.5^((t_"current" - t_"match") / 180) $

==== 2. VRS (Valve Regional Standing) Weight
HLTV assigns a `vrs_weight` score to events based on participating team rankings and prize pool. During data collection, we observed that not all events have an associated `vrs_weight`. Additionally, the raw `vrs_weight` values range from 0 to 1,000,000.

To address missing values and ensure consistent scaling, we assign higher importance to events featuring top-50 teams. Events without an assigned `vrs_weight` are initialized with a baseline weight of 0.1. The original scores are then normalized to the interval $[0.1, 10]$ using the following transformation:

$ w_"VRS" = 0.1 + ("vrs_weight" / 1000000) times 9.9 $

==== 3. Event Type Multiplier
Ranked matches (official Valve tournaments) receive higher weight than exhibition or online cups:

$ w_"type" = cases(
  1.5 quad &"if event_type = Ranked",
  1.0 quad &"otherwise"
) $

==== 4. Top-50 Team Participation
Matches featuring elite teams (HLTV Top 50) provide higher-quality training signal:

$ w_"elite" = cases(
  1.7 quad &"if has_top_50_teams = True",
  1.0 quad &"otherwise"
) $

The final *raw weight* is the product of these components:

$ w_"raw" = w_"VRS" times w_"recency" times w_"type" times w_"elite" $

To prevent extreme weight disparities (which can destabilize gradient-based learning), we apply log-normalization followed by min-max scaling to $[0, 1]$:

$ w_"final" = (log(1 + w_"raw") - log(1 + w_"min")) / (log(1 + w_"max") - log(1 + w_"min")) $

This produces a smooth, bounded weighting scheme where recent Major matches approach 1.0, while stale qualifier matches decay toward 0.0.

=== Elo Rating System with Dynamic K-Factor

We build upon the classical Elo rating framework originally developed for chess, adapting the formulation @glickman1999rating to the competitive context of CS2. Our objective is to capture both short-term team momentum and the intrinsic value of each match by incorporating the previously defined `event_weight`.

To model evolving team-strength trajectories, we implement a modified Elo system tailored to esports competition. Standard Elo formulations rely on fixed K-factors, which inadequately reflect the heterogeneous informativeness of matches across tournaments and competitive tiers. To address this limitation, we introduce event-aware K-factor scaling, allowing rating updates to be amplified or attenuated according to match importance, as determined by the event context.

==== Core Elo Mechanics
Each team maintains a scalar rating $R$, initialized at 1500. The expected win probability for team $i$ against team $j$ is:

$ E_i = 1 / (1 + 10^((R_j - R_i) \/ 400)) $

After a match with outcome $S_i \in {0, 1}$, where $0$ denotes a win by Team 1 and $1$ denotes a win by Team 2, the ratings are updated according to:

$ R_i^"new" = R_i^"old" + K dot (S_i - E_i) $

==== Dynamic K-Factor Adjustment
The K-factor modulates the magnitude of rating shifts. We scale the base $K = 20$ by the normalized event weight:

$ K_"effective" = 20 times (0.5 + w_"final") $

This ensures that high-stakes matches (Major playoffs) produce larger rating swings, while low-priority events contribute minimal noise. Additionally, we apply an *upset dampening* heuristic:

$ K_"effective" = cases(
  0.5 K_"effective" quad &"if" |R_i - R_j| > 400 "and favorite wins",
  K_"effective" quad &"otherwise"
) $

This prevents rating inflation when heavily favored teams defeat weaker opponents, while preserving full sensitivity to upsets.

#figure(
  image("images/teams_elos_over_time.png"),
  caption: [Elo rating trajectories of selected teams over time],
) <fig-teams-elos-over-time>

As shown in @fig-teams-elos-over-time, the Elo trajectories reflect the competitive performance of each team over the observed period. Team Vitality exhibits a pronounced increase between January and July 2025, corresponding to a dominant competitive phase in which it secured multiple tournament victories, including Major championships.  

Furia displays a more gradual progression for most of the timeline, followed by a sharp rise beginning in October 2025, coinciding with a streak of four championship wins.  

Finally, FaZe Clan shows relatively stable Elo dynamics throughout the year, with moderate fluctuations. However, a strong performance toward the end of the season results, culminating in a run to the Budapest Major Finals, where they faced Team Vitality.

==== Temporal Integration
Elo ratings are computed *chronologically* across all 43,060 match-maps, sorted by `match_date`. For each match, we record the *pre-match* Elo values of both teams (`t1_elo`, `t2_elo`), then update their ratings post-match. This ensures ratings reflect team strength *at the time of prediction*, avoiding leakage of future information.

\
\
\
\
\
\
\
=== Final Feature Space

The engineered dataset comprises 43,060 match-map instances with the following feature categories:

#figure(
  caption: [Engineered feature categories in the final match prediction dataset.],
  table(
    columns: (1fr, auto, 2fr),
    align: left + horizon,
    stroke: none,
    toprule,
    table.header([Category], [Count], [Examples]),
    midrule,
    [Team Performance Stats], [140], [`t1_kills_avg`, `t2_adr_median`, `t1_rating_3_dot_0_std`],
    [Elo Ratings], [2], [`t1_elo`, `t2_elo`],
    [Event Context], [1], [`event_weight`],
    [Map Encoding], [1], [`map_encoding` (0–9)],
    [Temporal], [1], [`match_date`],
    [Target Variable], [1], [`winner` (0=team_1, 1=team_2)],
    botrule,
  ),
) <tab-feature-summary>

The dataset is exported as `match_dataset.parquet` (43,060 rows × 147 columns) for downstream modeling.