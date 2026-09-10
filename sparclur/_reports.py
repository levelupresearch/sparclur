"""Native HTML reporting and evidence-bundle exports for SPARCLUR."""

from __future__ import annotations

import hashlib
import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from inspect import signature
from pathlib import Path
from typing import Any

import pandas as pd

from sparclur._parser import Parser
from sparclur._renderer import Renderer
from sparclur._roll_back import RollBack
from sparclur._text_compare import TextCompare
from sparclur._tracer import Tracer
from sparclur.parsers.present_parsers import get_sparclur_parsers
from sparclur.prc._viz import PRCViz


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _frame_html(frame: pd.DataFrame, empty_message: str) -> str:
    if frame.empty:
        return f'<p class="empty">{html.escape(empty_message)}</p>'
    return frame.to_html(index=False, escape=True, classes="report-table", border=0)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, default=str, sort_keys=True) + "\n", encoding="utf-8")


def _document_input(doc: str | Path | tuple[str | Path, str | None]) -> tuple[str, str | None]:
    if isinstance(doc, tuple):
        if len(doc) != 2:
            raise ValueError("Document tuples must contain (path, note)")
        return str(doc[0]), doc[1]
    return str(doc), None


@dataclass(frozen=True)
class _ReportInput:
    path: str
    note: str | None = None


class DocumentReport:
    """Analyze one PDF and write a readable report with reusable evidence data.

    The report collects the PTC, PXC, and PRC evidence that was previously
    produced by the Pweave integration, without requiring a notebook kernel.
    """

    def __init__(self,
                 doc: str | Path,
                 note: str | None = None,
                 parsers: list[str] | None = None,
                 parser_args: dict[str, dict[str, Any]] | None = None,
                 dpi: int = 72,
                 timeout: int | None = 30):
        self._input = _ReportInput(str(doc), note)
        self._parser_names = parsers
        self._parser_args = {} if parser_args is None else {
            name: dict(options) for name, options in parser_args.items()
        }
        self._dpi = dpi
        self._timeout = timeout
        self._analysis: dict[str, Any] | None = None

    @property
    def doc(self) -> str:
        return self._input.path

    @property
    def note(self) -> str | None:
        return self._input.note

    def _kwargs_for(self, parser: type[Parser]) -> dict[str, Any]:
        params = signature(parser.__init__).parameters
        kwargs = dict(self._parser_args.get(parser.get_name(), {}))
        kwargs["doc"] = self.doc
        if self._timeout is not None and "timeout" in params:
            kwargs["timeout"] = self._timeout
        if issubclass(parser, Renderer):
            if "dpi" in params:
                kwargs["dpi"] = self._dpi
            if "cache_renders" in params:
                kwargs["cache_renders"] = True
        return kwargs

    def analyze(self) -> dict[str, Any]:
        """Run selected available parsers and return structured report data."""
        if self._analysis is not None:
            return self._analysis

        source = Path(self.doc)
        if not source.is_file():
            raise FileNotFoundError(f"PDF not found: {source}")

        known = {parser.get_name(): parser for parser in get_sparclur_parsers()}
        if self._parser_names is None:
            available = {
                parser.get_name(): parser
                for parser in get_sparclur_parsers(check_parsers=True, parser_args=self._parser_args)
            }
            requested = list(available)
        else:
            requested = list(self._parser_names)
        unavailable = [name for name in requested if name not in known]
        parser_rows: list[dict[str, Any]] = []
        trace_rows: list[dict[str, Any]] = []
        text_by_parser: dict[str, dict[str, str]] = {}
        instances: dict[str, Parser] = {}
        renderers: dict[str, Renderer] = {}
        texters: dict[str, TextCompare] = {}

        for name in requested:
            parser_class = known.get(name)
            if parser_class is None:
                parser_rows.append({"parser": name, "status": "Unavailable", "validity": "", "error": "Not configured"})
                continue
            try:
                parser = parser_class(**self._kwargs_for(parser_class))
                instances[name] = parser
                validity = parser.validity.get("overall", {}).get("status", "Unknown")
                parser_rows.append({"parser": name, "status": "Analyzed", "validity": validity, "error": ""})
                if isinstance(parser, Tracer) and parser.can_trace:
                    for line, message in parser.cleaned.items():
                        trace_rows.append({"parser": name, "location": str(line), "message": str(message)})
                if isinstance(parser, TextCompare) and parser.can_extract_text:
                    texters[name] = parser
                    text_by_parser[name] = {str(page): str(text) for page, text in parser.get_text().items()}
                if isinstance(parser, Renderer) and parser.can_render:
                    renderers[name] = parser
            except Exception as error:
                parser_rows.append({"parser": name, "status": "Failed", "validity": "", "error": str(error)})

        pxc_frame = self._text_comparisons(texters)
        rollback = RollBack(self.doc)
        self._analysis = {
            "document": {
                "path": str(source.resolve()),
                "name": source.name,
                "size_bytes": source.stat().st_size,
                "sha256": _file_sha256(source),
                "note": self.note,
            },
            "requested_parsers": requested,
            "unavailable_parsers": unavailable,
            "parser_rows": parser_rows,
            "trace_rows": trace_rows,
            "text_by_parser": text_by_parser,
            "pxc": pxc_frame.to_dict(orient="records"),
            "renderers": renderers,
            "rollback": {
                "contains_updates": rollback.contains_updates,
                "num_versions": rollback.num_versions,
            },
        }
        return self._analysis

    @staticmethod
    def _text_comparisons(texters: dict[str, TextCompare]) -> pd.DataFrame:
        names = list(texters)
        if not names:
            return pd.DataFrame(columns=["parser"])
        rows = []
        for left in names:
            row: dict[str, Any] = {"parser": left}
            for right in names:
                if left == right:
                    row[right] = 1.0
                else:
                    try:
                        row[right] = 1.0 - texters[left].compare_text(texters[right])
                    except Exception as error:
                        row[right] = f"Error: {error}"
            rows.append(row)
        return pd.DataFrame(rows)

    def _write_bundle(self, directory: Path, index_name: str) -> Path:
        result = self.analyze()
        data_dir = directory / "data"
        figure_dir = directory / "figures"
        evidence_dir = directory / "evidence"
        for path in (directory, data_dir, figure_dir, evidence_dir):
            path.mkdir(parents=True, exist_ok=True)

        parser_frame = pd.DataFrame(result["parser_rows"], columns=["parser", "status", "validity", "error"])
        trace_frame = pd.DataFrame(result["trace_rows"], columns=["parser", "location", "message"])
        pxc_frame = pd.DataFrame(result["pxc"])
        parser_frame.to_csv(data_dir / "parsers.csv", index=False)
        trace_frame.to_csv(data_dir / "traces.csv", index=False)
        pxc_frame.to_csv(data_dir / "text-comparison.csv", index=False)
        _write_json(data_dir / "text.json", result["text_by_parser"])

        prc_frame = self._write_prc_evidence(result["renderers"], figure_dir)
        prc_frame.to_csv(data_dir / "render-comparison.csv", index=False)

        rollback = result["rollback"]
        if rollback["contains_updates"]:
            roll_back = RollBack(self.doc)
            predecessor = evidence_dir / "version-0.pdf"
            roll_back.save_version(0, str(predecessor))
            rollback["version_0_path"] = str(Path("evidence") / predecessor.name)
        _write_json(data_dir / "rollback.json", rollback)

        manifest = {
            "format": "sparclur-evidence-bundle-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sparclur_version": __import__("sparclur").__version__,
            "parser_args": self._parser_args,
            "dpi": self._dpi,
            "timeout": self._timeout,
            "document": result["document"],
            "requested_parsers": result["requested_parsers"],
            "unavailable_parsers": result["unavailable_parsers"],
        }
        _write_json(directory / "manifest.json", manifest)
        _write_json(data_dir / "report.json", {key: value for key, value in result.items() if key != "renderers"})

        index_path = directory / index_name
        index_path.write_text(self._html(result, parser_frame, trace_frame, pxc_frame, prc_frame), encoding="utf-8")
        return index_path

    def _write_prc_evidence(self, renderers: dict[str, Renderer], figure_dir: Path) -> pd.DataFrame:
        columns = ["left", "right", "page", "similarity"]
        if len(renderers) < 2:
            return pd.DataFrame(columns=columns)
        try:
            viz = PRCViz(doc_path=self.doc, renderers=list(renderers.values()), dpi=self._dpi)
            rows = []
            for (left, right), page_sims in viz._sims.items():
                for page, similarity in page_sims.items():
                    rows.append({"left": left, "right": right, "page": page, "similarity": similarity.sim})
            frame = pd.DataFrame(rows, columns=columns)
            if frame.empty:
                return frame
            sim_figure = viz.plot_sims(width=9, height=4)
            sim_figure.savefig(figure_dir / "prc-similarity.png", dpi=160, bbox_inches="tight")
            worst = frame.loc[frame["similarity"].idxmin()]
            diff_figure = viz.display(
                page=int(worst["page"]),
                renderers=[(worst["left"], worst["right"])],
                width=12,
                height=5,
            )
            diff_figure.savefig(figure_dir / "prc-worst-page.png", dpi=160, bbox_inches="tight")
            return frame
        except Exception as error:
            return pd.DataFrame([{"left": "", "right": "", "page": "", "similarity": f"Error: {error}"}])

    def _html(self,
              result: dict[str, Any],
              parser_frame: pd.DataFrame,
              trace_frame: pd.DataFrame,
              pxc_frame: pd.DataFrame,
              prc_frame: pd.DataFrame) -> str:
        document = result["document"]
        rollback = result["rollback"]
        figures = ""
        if not prc_frame.empty and isinstance(prc_frame.iloc[0].get("similarity"), (float, int)):
            figures = (
                '<div class="figures"><figure><img src="figures/prc-similarity.png" alt="Renderer similarity by page">'
                '<figcaption>Renderer similarity by page</figcaption></figure>'
                '<figure><img src="figures/prc-worst-page.png" alt="Lowest-similarity renderer comparison">'
                '<figcaption>Lowest-similarity renderer comparison</figcaption></figure></div>'
            )
        note = "" if not document["note"] else f'<p class="note">{html.escape(document["note"])}</p>'
        rollback_summary = "No incremental updates detected."
        if rollback["contains_updates"]:
            rollback_summary = (
                f'{rollback["num_versions"]} incremental versions detected. '
                '<a href="evidence/version-0.pdf">Extracted version 0</a> is included.'
            )
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SPARCLUR report — {html.escape(document["name"])}</title>
<style>
body {{ background: #eef2f7; color: #1e293b; font-family: system-ui, sans-serif; line-height: 1.45; margin: 0; }}
main {{ background: white; box-shadow: 0 8px 28px #cbd5e180; margin: 28px auto; max-width: 1040px; padding: 40px; }}
h1 {{ margin: 4px 0; }} h2 {{ border-bottom: 1px solid #dbe4ee; margin-top: 34px; padding-bottom: 6px; }}
.eyebrow {{ color: #315c87; font-size: .75rem; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; }}
.muted, .empty {{ color: #64748b; }} .note {{ background: #eff6ff; border-left: 4px solid #3b82f6; padding: 10px 12px; }}
.summary {{ display: grid; gap: 12px; grid-template-columns: repeat(3, 1fr); margin: 22px 0; }}
.metric {{ border: 1px solid #dbe4ee; padding: 12px; }} .metric span {{ color: #64748b; display: block; font-size: .8rem; }}
.report-table {{ border-collapse: collapse; font-size: .88rem; width: 100%; }} .report-table td, .report-table th {{ border: 1px solid #dbe4ee; padding: 7px; text-align: left; vertical-align: top; }} .report-table th {{ background: #eff6ff; }}
.figures {{ display: grid; gap: 18px; grid-template-columns: 1fr 1fr; }} figure {{ margin: 0; }} img {{ border: 1px solid #dbe4ee; max-width: 100%; }} figcaption {{ color: #64748b; font-size: .85rem; }}
footer {{ border-top: 1px solid #dbe4ee; color: #64748b; font-size: .85rem; margin-top: 36px; padding-top: 14px; }}
@media (max-width: 680px) {{ main {{ margin: 0; padding: 20px; }} .summary, .figures {{ grid-template-columns: 1fr; }} }}
</style></head><body><main>
<div class="eyebrow">SPARCLUR evidence dossier</div><h1>{html.escape(document["name"])}</h1>
<p class="muted">SHA-256: {html.escape(document["sha256"])} · {document["size_bytes"]:,} bytes</p>{note}
<section class="summary"><div class="metric"><span>Analyzed parsers</span><strong>{len(parser_frame[parser_frame["status"] == "Analyzed"])}</strong></div><div class="metric"><span>Trace messages</span><strong>{len(trace_frame)}</strong></div><div class="metric"><span>Rollback</span><strong>{"Detected" if rollback["contains_updates"] else "None"}</strong></div></section>
<h2>Parser validity</h2>{_frame_html(parser_frame, "No configured parsers were available.")}
<h2>Parser trace comparator</h2>{_frame_html(trace_frame, "No normalized trace messages were collected.")}
<h2>Parser text comparator</h2>{_frame_html(pxc_frame, "No text-capable parsers were available.")}
<h2>PDF renderer comparator</h2>{_frame_html(prc_frame, "At least two renderers are required for a render comparison.")}{figures}
<h2>Rollback</h2><p>{rollback_summary}</p>
<footer>Evidence: <a href="manifest.json">manifest</a> · <a href="data/report.json">report JSON</a> · <a href="data/parsers.csv">parser CSV</a> · <a href="data/traces.csv">trace CSV</a> · <a href="data/text-comparison.csv">text CSV</a> · <a href="data/render-comparison.csv">render CSV</a></footer>
</main></body></html>"""

    def write_bundle(self, directory: str | Path) -> Path:
        """Write ``index.html``, figures, structured tables, and provenance data."""
        return self._write_bundle(Path(directory), "index.html")

    def write_html(self, path: str | Path) -> Path:
        """Write an HTML dossier and its sibling evidence assets."""
        target = Path(path)
        if target.suffix.lower() != ".html":
            target = target / "index.html"
        return self._write_bundle(target.parent, target.name)


class BatchReport:
    """Create a triage index with a complete evidence dossier for each PDF."""

    def __init__(self,
                 docs: list[str | Path | tuple[str | Path, str | None]],
                 **document_options: Any):
        self._docs = [_document_input(doc) for doc in docs]
        self._document_options = document_options

    def write_bundle(self, directory: str | Path) -> Path:
        directory = Path(directory)
        documents_dir = directory / "documents"
        summaries = []
        for index, (path, note) in enumerate(self._docs, start=1):
            report = DocumentReport(path, note=note, **self._document_options)
            analysis = report.analyze()
            dossier = report.write_bundle(documents_dir / f"{index:03d}")
            parser_frame = pd.DataFrame(analysis["parser_rows"], columns=["parser", "status", "validity", "error"])
            validity = ", ".join(
                sorted({value for value in parser_frame.get("validity", []) if value})
            ) or "Unavailable"
            summaries.append({
                "document": analysis["document"]["name"],
                "validity": validity,
                "trace_messages": len(analysis["trace_rows"]),
                "rollback_versions": analysis["rollback"]["num_versions"],
                "report": str(dossier.relative_to(directory)),
            })
        directory.mkdir(parents=True, exist_ok=True)
        data_dir = directory / "data"
        data_dir.mkdir(exist_ok=True)
        summary_frame = pd.DataFrame(summaries)
        summary_frame.to_csv(data_dir / "summary.csv", index=False)
        links = "".join(
            f'<tr><td><a href="{html.escape(row["report"])}">{html.escape(row["document"])}</a></td>'
            f'<td>{html.escape(row["validity"])}</td><td>{row["trace_messages"]}</td><td>{row["rollback_versions"]}</td></tr>'
            for row in summaries
        )
        (directory / "index.html").write_text(
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>SPARCLUR batch report</title>"
            "<style>body{font-family:system-ui,sans-serif;margin:32px;color:#1e293b}table{border-collapse:collapse;width:100%}td,th{border:1px solid #dbe4ee;padding:8px;text-align:left}th{background:#eff6ff}</style>"
            "</head><body><h1>SPARCLUR batch triage</h1><p>Each document links to a self-contained evidence dossier.</p>"
            "<table><tr><th>Document</th><th>Validity</th><th>Trace messages</th><th>Rollback versions</th></tr>"
            + links + "</table><p><a href=\"data/summary.csv\">Download summary CSV</a></p></body></html>",
            encoding="utf-8",
        )
        _write_json(directory / "manifest.json", {
            "format": "sparclur-batch-evidence-bundle-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "documents": summaries,
        })
        return directory / "index.html"

    def write_html(self, path: str | Path) -> Path:
        target = Path(path)
        return self.write_bundle(target.parent if target.suffix else target)


class SparclurReport:
    """Compatibility facade for the former Pweave ``SparclurReport`` API.

    ``generate_report`` now creates a native HTML evidence bundle and returns
    its index path. ``kernel`` and ``sparclur_path`` are accepted for source
    compatibility but are not used.
    """

    def __init__(self,
                 docs: str | Path | tuple[str | Path, str | None] | list[str | Path | tuple[str | Path, str | None]],
                 save_path: str | Path,
                 kernel: str = "python3",
                 title: str = "SPARCLUR Report",
                 sparclur_path: str | None = None,
                 **document_options: Any):
        self._docs = docs if isinstance(docs, list) else [docs]
        self._save_path = Path(save_path)
        self._title = title
        self._kernel = kernel
        self._sparclur_path = sparclur_path
        self._document_options = document_options

    def generate_report(self) -> Path:
        target = self._save_path.with_suffix(".html") if self._save_path.suffix else self._save_path
        if len(self._docs) == 1:
            path, note = _document_input(self._docs[0])
            return DocumentReport(path, note=note, **self._document_options).write_html(target)
        return BatchReport(self._docs, **self._document_options).write_html(target)
