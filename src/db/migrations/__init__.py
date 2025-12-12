import psycopg2
from psycopg2 import sql
import logging
from typing import List
from datetime import datetime

logger = logging.getLogger(__name__)


class Migration:
    def __init__(self, version: int, name: str, up_sql: str, down_sql: str = ""):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql


class MigrationManager:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "cs2_stats",
        user: str = "marcelinho",
        password: str = "molodoy",
    ):
        self.connection_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }
        self.migrations: List[Migration] = []

    def get_connection(self):
        return psycopg2.connect(**self.connection_params)

    def register_migration(self, migration: Migration):
        self.migrations.append(migration)

    def migrate(self):
        for migration in self.migrations:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(migration.up_sql)
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
                event_id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            );

            CREATE TABLE teams (
                team_id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            );

            CREATE TABLE players (
                player_id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            );

            CREATE TABLE matches (
                match_id VARCHAR(255) PRIMARY KEY,
                event_id VARCHAR(255) REFERENCES events(event_id),
                match_date TIMESTAMP WITH TIME ZONE NOT NULL,
                team_1_id VARCHAR(255) REFERENCES teams(team_id),
                team_2_id VARCHAR(255) REFERENCES teams(team_id),
                team_1_map_score INT DEFAULT 0,
                team_2_map_score INT DEFAULT 0,
                team_winner_id VARCHAR(255) REFERENCES teams(team_id)
            );


            CREATE TABLE vetos (
                match_id VARCHAR(255) PRIMARY KEY REFERENCES matches(match_id) ON DELETE CASCADE,
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
                map_stat_id VARCHAR(255) PRIMARY KEY,
                match_id VARCHAR(255) NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
                map_name VARCHAR(100) NOT NULL,
                team_1_score INT NOT NULL,
                team_2_score INT NOT NULL,
                team_1_ct_score INT,
                team_1_tr_score INT,
                team_2_ct_score INT,
                team_2_tr_score INT,
                picked_by VARCHAR(20) CHECK (picked_by IN ('team_1', 'team_2', 'leftover')),
                starting_ct VARCHAR(20) CHECK (starting_ct IN ('team_1', 'team_2'))
            );

            CREATE TABLE player_map_stats (
                map_stat_id VARCHAR(255) NOT NULL REFERENCES map_stats(map_stat_id) ON DELETE CASCADE,
                player_id VARCHAR(255) NOT NULL REFERENCES players(player_id),
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

    return manager


def main():
    manager = setup_migrations()
    manager.migrate()


if __name__ == "__main__":
    main()
