import psycopg
import logging
from typing import List, cast, LiteralString

from conf import get_connection_params

logger = logging.getLogger(__name__)


class Migration:
    def __init__(self, version: int, name: str, up_sql: str, down_sql: str = ""):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql


class MigrationManager:
    def __init__(self, connection_params: dict | None = None):
        """
        Initialize the migration manager.

        Args:
            connection_params: Optional dict with connection parameters.
                             If None, uses config from db.config module.
        """
        if connection_params is None:
            connection_params = get_connection_params()

        # Build connection string for psycopg3
        self.conninfo = (
            f"host={connection_params.get('host', 'localhost')} "
            f"port={connection_params.get('port', 5432)} "
            f"user={connection_params.get('user', 'postgres')} "
            f"password={connection_params.get('password', '')} "
            f"dbname={connection_params.get('dbname', 'postgres')} "
            f"sslmode={connection_params.get('sslmode', 'prefer')}"
        )
        self.migrations: List[Migration] = []

    def get_connection(self):
        return psycopg.connect(self.conninfo)

    def register_migration(self, migration: Migration):
        self.migrations.append(migration)

    def migrate(self):
        for migration in self.migrations:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(cast(LiteralString, migration.up_sql))
                    conn.commit()
                logger.info(f"✓ Migration {migration.version} applied successfully")
            except Exception as e:
                logger.error(f"✗ Migration {migration.version} failed: {e}")
                raise


def setup_migrations() -> MigrationManager:
    manager = MigrationManager()
    manager.register_migration(
        Migration(
            version=1,
            name="create_base_tables",
            up_sql="""
            CREATE TABLE events (
                event_id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            );

            CREATE TABLE teams (
                team_id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            );

            CREATE TABLE players (
                player_id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            );

            CREATE TABLE matches (
                match_id SERIAL PRIMARY KEY,
                event_id INT REFERENCES events(event_id) ON DELETE CASCADE,
                match_date TIMESTAMP WITH TIME ZONE NOT NULL,
                team_1_id INT REFERENCES teams(team_id),
                team_2_id INT REFERENCES teams(team_id),
                team_1_map_score INT DEFAULT 0,
                team_2_map_score INT DEFAULT 0,
                team_winner_id INT REFERENCES teams(team_id)
            );


            CREATE TABLE vetos (
                match_id  INT PRIMARY KEY REFERENCES matches(match_id) ON DELETE CASCADE,
                best_of INT CHECK (best_of IN (1, 3, 5)),
                t1_removed_1 VARCHAR(100),
                t2_removed_1 VARCHAR(100),
                t1_picked_1  VARCHAR(100),
                t2_picked_1  VARCHAR(100),
                t1_removed_2 VARCHAR(100),
                t2_removed_2 VARCHAR(100),
                t1_picked_2  VARCHAR(100),
                t2_picked_2  VARCHAR(100),
                t1_removed_3 VARCHAR(100),
                t2_removed_3 VARCHAR(100),
                left_over_map VARCHAR(100)
            );

            CREATE TABLE map_stats (
                map_stat_id SERIAL PRIMARY KEY,
                match_id  INT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
                map_name VARCHAR(100) NOT NULL,
                team_1_score INT NOT NULL,
                team_2_score INT NOT NULL,
                team_1_overtime_score INT,
                team_2_overtime_score INT,
                team_1_ct_score INT NOT NULL,
                team_1_tr_score INT NOT NULL,
                team_2_ct_score INT NOT NULL,
                team_2_tr_score INT NOT NULL,
                picked_by VARCHAR(20) CHECK (picked_by IN ('team_1', 'team_2', 'leftover')),
                starting_ct VARCHAR(20) CHECK (starting_ct IN ('team_1', 'team_2'))
            );

            CREATE TABLE player_map_stats (
                map_stat_id  INT NOT NULL REFERENCES map_stats(map_stat_id) ON DELETE CASCADE,
                player_id INT NOT NULL REFERENCES players(player_id),
                PRIMARY key(map_stat_id, player_id), 
                opening_kills_ct INT DEFAULT 0,
                opening_deaths_ct INT DEFAULT 0,
                multikills_ct INT DEFAULT 0,
                kast_ct DECIMAL(5, 2),
                clutches_ct INT DEFAULT 0,
                kills_ct INT DEFAULT 0,
                headshot_kills_ct INT DEFAULT 0,
                assists_ct INT DEFAULT 0,
                flash_assists_ct INT DEFAULT 0,
                deaths_ct INT DEFAULT 0,
                traded_deaths_ct INT DEFAULT 0,
                adr_ct DECIMAL(6, 2),
                swing_ct DECIMAL(6, 2),
                rating_3_dot_0_ct DECIMAL(5, 2),
                opening_kills_tr INT DEFAULT 0,
                opening_deaths_tr INT DEFAULT 0,
                multikills_tr INT DEFAULT 0,
                kast_tr DECIMAL(5, 2),
                clutches_tr INT DEFAULT 0,
                kills_tr INT DEFAULT 0,
                headshot_kills_tr INT DEFAULT 0,
                assists_tr INT DEFAULT 0,
                flash_assists_tr INT DEFAULT 0,
                deaths_tr INT DEFAULT 0,
                traded_deaths_tr INT DEFAULT 0,
                adr_tr DECIMAL(6, 2),
                swing_tr DECIMAL(6, 2),
                rating_3_dot_0_tr DECIMAL(5, 2)
            );
            """,
        )
    )

    manager.register_migration(
        Migration(
            version=2,
            name="add_unique_constraints",
            up_sql="""
            ALTER TABLE events
                ADD COLUMN IF NOT EXISTS start_date TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS end_date TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS invite_date TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS invite_date TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS vrs_date TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS vrs_weight INT DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS teams INT DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS total_prize_pool DECIMAL DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS player_share DECIMAL DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS location VARCHAR(100) DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS event_type VARCHAR(100) DEFAULT NULL,
                ADD COLUMN IF NOT EXISTS has_top_50_teams BOOLEAN DEFAULT false;
            """,
        )
    )

    manager.register_migration(
        Migration(
            version=3,
            name="add_team_id_to_player_map_stats",
            up_sql="""
            ALTER TABLE player_map_stats
                ADD COLUMN IF NOT EXISTS team_id INT REFERENCES teams(team_id);
            """,
        )
    )

    return manager


def main():
    manager = setup_migrations()
    manager.migrate()


if __name__ == "__main__":
    main()
