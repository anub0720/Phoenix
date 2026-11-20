
"""Read-only PostgreSQL query execution inside a Phoenix restore container."""

import subprocess


class PostgresValidationAdapter:
    """Executes read-only scalar queries using psql inside Docker."""

    def __init__(
        self,
        database_name: str = "phoenix_restore",
        database_user: str = "postgres",
        query_timeout: int = 30,
    ) -> None:
        self.database_name = database_name
        self.database_user = database_user
        self.query_timeout = query_timeout

    def execute_scalar(self, container_id: str, query: str) -> str:
        """Execute one SELECT statement and return its scalar output.

        Queries are restricted to a single SELECT statement and executed
        inside an explicitly read-only transaction.
        """

        normalized_query = query.strip()

        if not container_id or not container_id.strip():
            raise ValueError("Container ID cannot be empty.")

        if not normalized_query:
            raise ValueError("Query cannot be empty.")

        if not normalized_query.lower().startswith("select "):
            raise ValueError("Only SELECT queries are permitted.")

        if ";" in normalized_query:
            raise ValueError("Multiple SQL statements are not permitted.")

        readonly_query = (
            "BEGIN TRANSACTION READ ONLY; "
            f"{normalized_query}; "
            "COMMIT;"
        )

        command = [
            "docker",
            "exec",
            "--user",
            self.database_user,
            container_id,
            "psql",
            "--username",
            self.database_user,
            "--dbname",
            self.database_name,
            "--no-psqlrc",
            "--quiet",
            "--tuples-only",
            "--no-align",
            "--set=ON_ERROR_STOP=1",
            "--command",
            readonly_query,
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.query_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError(
                "PostgreSQL validation query exceeded its timeout."
            ) from error

        if result.returncode != 0:
            raise RuntimeError(
                "PostgreSQL validation query failed: "
                f"{result.stderr.strip()}"
            )

        return result.stdout.strip()
