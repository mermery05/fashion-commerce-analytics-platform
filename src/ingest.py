from pathlib import Path
import duckdb


def csv_to_bronze(csv_path: str, table: str) -> dict:
    out_dir = Path(f"data/bronze/{table}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "part.parquet"

    con = duckdb.connect()
    con.execute(f"""
        COPY (
          SELECT *, now() AS _ingested_at, '{Path(csv_path).name}' AS _source_file
          FROM read_csv('{csv_path}', header=true, all_varchar=true,
                        ignore_errors=true, store_rejects=true)
        ) TO '{out}' (FORMAT PARQUET)
    """)
    rows = con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0]
    try:
        rejected = con.execute("SELECT count(*) FROM reject_errors").fetchone()[0]
    except duckdb.Error:
        rejected = 0
    return {"rows_loaded": rows, "rows_rejected": rejected}
