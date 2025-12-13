## [1.1.1](https://github.com/talDoFlemis/clutch-or-predict/compare/v1.1.0...v1.1.1) (2025-12-13)

### Code Refactoring

* add overtime handling ([b4c1d12](https://github.com/talDoFlemis/clutch-or-predict/commit/b4c1d12ca8504ac9ef8d9abaeb80bc74e9ba5147))
* **frontier:** only call service if new entries ([caf83d3](https://github.com/talDoFlemis/clutch-or-predict/commit/caf83d3e71f0dd696a495b954a234977a0b0ca54))
* **migrations:** add overtime rounds ([2713ea6](https://github.com/talDoFlemis/clutch-or-predict/commit/2713ea68f93c6465d28876e32dfcbb81d48140a9))

## [1.1.0](https://github.com/talDoFlemis/clutch-or-predict/compare/v1.0.2...v1.1.0) (2025-12-12)

### Features

* add psycopg and psycopgpool ([a961ea6](https://github.com/talDoFlemis/clutch-or-predict/commit/a961ea6dee42268c3902ea6aa17c5a5feff21ca2))
* insert data from celery ([3f52690](https://github.com/talDoFlemis/clutch-or-predict/commit/3f526903150231ce432bff3f20739d8a82545203))
* make frontier use new redis ([82c3dbd](https://github.com/talDoFlemis/clutch-or-predict/commit/82c3dbdb8d62f52196cc591b5ed155f766ff8262))

### Bug Fixes

* **player:** break when kast is 0 ([00d6ab5](https://github.com/talDoFlemis/clutch-or-predict/commit/00d6ab5edbbe27402332d2371e9ab9fbf6339b39))

### Code Refactoring

* **migrations:** use psycopg3 ([5203cbf](https://github.com/talDoFlemis/clutch-or-predict/commit/5203cbfa0d3605911d9d2f02b6cd68f1f7877da6))

## [1.0.2](https://github.com/talDoFlemis/clutch-or-predict/compare/v1.0.1...v1.0.2) (2025-12-12)

### Bug Fixes

* **release:** remove arm from browser ([2e19ff9](https://github.com/talDoFlemis/clutch-or-predict/commit/2e19ff9a325a8c192b472aafb650179c147cb7cc))

## [1.0.1](https://github.com/talDoFlemis/clutch-or-predict/compare/v1.0.0...v1.0.1) (2025-12-12)

### Bug Fixes

* **release:** bad dockerfile for worker ([8607b30](https://github.com/talDoFlemis/clutch-or-predict/commit/8607b30b7d8a471c57ddd8f9a36c718fea0eeed0))

## 1.0.0 (2025-12-12)

### Features

* add browser module ([37a9c2d](https://github.com/talDoFlemis/clutch-or-predict/commit/37a9c2d608a8c562367a0166d4970ea24e0fb0a0))
* add browser on docker ([3a8a7c8](https://github.com/talDoFlemis/clutch-or-predict/commit/3a8a7c8ff6391f2d8314b2ad444da0acebbe17c0))
* add celery ([88585d8](https://github.com/talDoFlemis/clutch-or-predict/commit/88585d879c6b112eac2488d06fe3b35b32bcb7b6))
* add concurrency settings to celery ([041ec4d](https://github.com/talDoFlemis/clutch-or-predict/commit/041ec4d385e94edba95d2b09d70317b24ebcd42b))
* add dynaconf to celery and browser ([930ee9a](https://github.com/talDoFlemis/clutch-or-predict/commit/930ee9ad7341843866d40aa6bdb672de2d46fc70))
* add frontier ([7e2136b](https://github.com/talDoFlemis/clutch-or-predict/commit/7e2136bffa7de08c09fbea6b3aa7538192df1c33))
* add map ([92a2f89](https://github.com/talDoFlemis/clutch-or-predict/commit/92a2f896890ce7d09979a4d801d55542e5273adc))
* add match result scraping ([4d6873c](https://github.com/talDoFlemis/clutch-or-predict/commit/4d6873cf0395e075988689f523c5bd86efc3f914))
* add page pool ([442fdb1](https://github.com/talDoFlemis/clutch-or-predict/commit/442fdb1f5ce977d9925e60159c12b8ea6eb1f7d6))
* add player stats processing ([78c2a6e](https://github.com/talDoFlemis/clutch-or-predict/commit/78c2a6ef9dda115296793fdfe8a4d788302bfcfd))
* add release ([93055b9](https://github.com/talDoFlemis/clutch-or-predict/commit/93055b911334677db7abf32b371cbf9359e97c48))
* add scraper browser ([1078c7d](https://github.com/talDoFlemis/clutch-or-predict/commit/1078c7dfb1a1f45f45f90857a3646f5f82b8e035))
* add timeout to pool pages ([b177dce](https://github.com/talDoFlemis/clutch-or-predict/commit/b177dce07f916b232c146a7080736d76a4ce9c3d))
* add vetos ([4f2f467](https://github.com/talDoFlemis/clutch-or-predict/commit/4f2f467d049be82433565ca7046236d7c3315e33))
* adding db conn ([5a8a6b3](https://github.com/talDoFlemis/clutch-or-predict/commit/5a8a6b335c1f3bfdebb857733fd2dea46973ed77))
* adding match_id to maps ([b08c642](https://github.com/talDoFlemis/clutch-or-predict/commit/b08c642de61214e520f9a4135f8142177f2c8f5f))
* adding migration ([22dd23d](https://github.com/talDoFlemis/clutch-or-predict/commit/22dd23d22d60578f2f637373c00fd606e993d807))
* make every scraper use another page ([c16f3d1](https://github.com/talDoFlemis/clutch-or-predict/commit/c16f3d19afd00e0268302eeab731c385d67c70a9))
* make worker run in docker ([03021af](https://github.com/talDoFlemis/clutch-or-predict/commit/03021afdc2d2340dad0e767987be104aa7e6b456))
* **pool:** add close all pages fn ([1982b68](https://github.com/talDoFlemis/clutch-or-predict/commit/1982b6878e0a0409af393b29daba31c72bf098b2))

### Bug Fixes

* **pool:** some pages are not tracked ([a4141f8](https://github.com/talDoFlemis/clutch-or-predict/commit/a4141f86e6afa87b2184902b20fa1987bccfe1b2))

### Code Refactoring

* celery make code concurrently ([5fcce84](https://github.com/talDoFlemis/clutch-or-predict/commit/5fcce8411c5ce138e717d8b9508c92ffbe2997ad))
* **celery:** process each scrape in a different task ([9df6b8c](https://github.com/talDoFlemis/clutch-or-predict/commit/9df6b8c4f693c64280ed5bfffcffef09d20e512e))
* create simple example ([5138c8a](https://github.com/talDoFlemis/clutch-or-predict/commit/5138c8a451fa5125b06e6478445b804a39a8ca63))
* dont depend on match result to process maps and vetos ([44c5d78](https://github.com/talDoFlemis/clutch-or-predict/commit/44c5d78f88ce94df63744a3073c3c1e92ae2a3ae))
* **map:** use parsel instead of playwright locators ([9d70ff7](https://github.com/talDoFlemis/clutch-or-predict/commit/9d70ff752146dacf2ae9685e9cddb4ec21554268))
* **match:** use parsel instead of playwright locators ([72fe430](https://github.com/talDoFlemis/clutch-or-predict/commit/72fe430f85b3dc629abd3812b63d6a93bab84383))
* **player:** use parsel instead of playwright selectors ([8c2cb67](https://github.com/talDoFlemis/clutch-or-predict/commit/8c2cb67c8ed72db4ac01ea0cd2be08836185ee2b))
* **pool:** make expansion simpler ([671fbde](https://github.com/talDoFlemis/clutch-or-predict/commit/671fbde742075bc293cdf894ff2026ae7972ed9c))
* remove tasks and name just celery ([8e6ced5](https://github.com/talDoFlemis/clutch-or-predict/commit/8e6ced50d6188ff2a034f137e8b75e7843b114da))
* **vetos:** get team names from selector ([bfbd30d](https://github.com/talDoFlemis/clutch-or-predict/commit/bfbd30d7d584934bff6184543ec6a98336adc787))
* **vetos:** use parsel instead of playwright locators ([a2b2045](https://github.com/talDoFlemis/clutch-or-predict/commit/a2b20459d7ab017e3e63f5260f34ec8b7425b3f9))
