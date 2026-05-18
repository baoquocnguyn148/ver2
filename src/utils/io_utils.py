from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path
from typing import Iterable

import pandas as pd

from src import config


class DataIO:
    """Read and write pipeline artifacts in local mode or S3 mode.

    Local mode keeps the existing repo-relative behavior. S3 mode uses
    awswrangler for tabular S3 reads/writes and boto3 for binary artifacts such
    as formatted Excel workbooks.
    """

    def __init__(
        self,
        local_mode: bool | None = None,
        bucket: str | None = None,
        raw_key: str | None = None,
        curated_prefix: str | None = None,
        output_prefix: str | None = None,
        project_root: Path | None = None,
    ) -> None:
        self.local_mode = config.LOCAL_MODE if local_mode is None else local_mode
        self.bucket = bucket or config.S3_BUCKET
        self.raw_key = raw_key or config.RAW_KEY
        self.curated_prefix = self._clean_prefix(curated_prefix or config.CURATED_PREFIX)
        self.output_prefix = self._clean_prefix(output_prefix or config.OUTPUT_PREFIX)
        self.project_root = project_root or config.PROJECT_ROOT

        if not self.local_mode and not self.bucket:
            raise ValueError("S3_BUCKET is required when LOCAL_MODE=false.")

    @staticmethod
    def _clean_prefix(prefix: str) -> str:
        return prefix.strip("/")

    def _s3_uri(self, key: str) -> str:
        key = key.lstrip("/")
        return f"s3://{self.bucket}/{key}"

    def _require_awswrangler(self):
        try:
            import awswrangler as wr
        except ImportError as exc:  # pragma: no cover - depends on cloud deps
            raise ImportError(
                "awswrangler is required for S3 mode. Install requirements.txt first."
            ) from exc
        return wr

    def _require_boto3(self):
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - depends on cloud deps
            raise ImportError("boto3 is required for uploading binary files to S3.") from exc
        return boto3

    def read_raw_excel(self, sheet_name: str):
        """Read the raw Excel file from the repo or s3://bucket/raw_key."""
        if self.local_mode:
            path = self.project_root / Path(self.raw_key).name
            print(f"[DataIO] Reading local Excel: {path}")
            return pd.read_excel(path, sheet_name=sheet_name)

        wr = self._require_awswrangler()
        path = self._s3_uri(self.raw_key)
        print(f"[DataIO] Reading S3 Excel: {path}")
        try:
            return wr.s3.read_excel(path=path, sheet_name=sheet_name)
        except Exception as exc:
            raise RuntimeError(f"Failed to read raw Excel from {path}: {exc}") from exc

    def read_excel(self, key: str, sheet_name: str):
        """Read an Excel workbook from a local path or an S3 key."""
        if self.local_mode:
            path = self.project_root / key
            print(f"[DataIO] Reading local Excel: {path}")
            return pd.read_excel(path, sheet_name=sheet_name)

        wr = self._require_awswrangler()
        path = self._s3_uri(key)
        print(f"[DataIO] Reading S3 Excel: {path}")
        try:
            return wr.s3.read_excel(path=path, sheet_name=sheet_name)
        except Exception as exc:
            raise RuntimeError(f"Failed to read Excel from {path}: {exc}") from exc

    def save_parquet(
        self,
        table_name: str,
        df: pd.DataFrame,
        partition_cols: Iterable[str] | None = None,
    ) -> str:
        """Save a curated table as a Parquet dataset."""
        partition_cols = list(partition_cols or [])

        if self.local_mode:
            path = self.project_root / self.curated_prefix / table_name
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)
            print(f"[DataIO] Writing local Parquet dataset: {path}")
            if partition_cols:
                df.to_parquet(path, index=False, partition_cols=partition_cols)
            else:
                df.to_parquet(path / f"{table_name}.parquet", index=False)
            return str(path)

        wr = self._require_awswrangler()
        path = self._s3_uri(f"{self.curated_prefix}/{table_name}/")
        print(f"[DataIO] Writing S3 Parquet dataset: {path}")
        try:
            wr.s3.to_parquet(
                df=df,
                path=path,
                dataset=True,
                mode="overwrite",
                index=False,
                partition_cols=partition_cols or None,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to write Parquet dataset to {path}: {exc}") from exc
        return path

    def save_csv(self, name: str, df: pd.DataFrame, prefix: str | None = None) -> str:
        """Save a CSV artifact under the selected prefix."""
        prefix = self._clean_prefix(prefix or self.output_prefix)
        filename = name if name.endswith(".csv") else f"{name}.csv"

        if self.local_mode:
            path = self.project_root / prefix / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            print(f"[DataIO] Writing local CSV: {path}")
            df.to_csv(path, index=False, encoding="utf-8-sig")
            return str(path)

        wr = self._require_awswrangler()
        path = self._s3_uri(f"{prefix}/{filename}")
        print(f"[DataIO] Writing S3 CSV: {path}")
        try:
            wr.s3.to_csv(df=df, path=path, index=False, encoding="utf-8-sig")
        except Exception as exc:
            raise RuntimeError(f"Failed to write CSV to {path}: {exc}") from exc
        return path

    def save_excel(self, name: str, sheets: dict[str, pd.DataFrame], prefix: str | None = None) -> str:
        """Save a multi-sheet Excel artifact locally or to S3."""
        prefix = self._clean_prefix(prefix or self.output_prefix)
        filename = name if name.endswith(".xlsx") else f"{name}.xlsx"

        if self.local_mode:
            path = self.project_root / prefix / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            print(f"[DataIO] Writing local Excel: {path}")
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            return str(path)

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        buffer.seek(0)

        s3 = self._require_boto3().client("s3")
        key = f"{prefix}/{filename}"
        print(f"[DataIO] Writing S3 Excel: {self._s3_uri(key)}")
        try:
            s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=buffer.getvalue(),
                ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to write Excel to {self._s3_uri(key)}: {exc}") from exc
        return self._s3_uri(key)

    def upload_file(self, local_path: str | Path, key: str) -> str:
        """Upload an already-created file to S3, or return its path in local mode."""
        local_path = Path(local_path)
        if self.local_mode:
            return str(local_path)

        s3 = self._require_boto3().client("s3")
        key = key.lstrip("/")
        destination = self._s3_uri(key)
        print(f"[DataIO] Uploading file: {local_path} -> {destination}")
        try:
            s3.upload_file(str(local_path), self.bucket, key)
        except Exception as exc:
            raise RuntimeError(f"Failed to upload {local_path} to {destination}: {exc}") from exc
        return destination
