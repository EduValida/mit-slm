from __future__ import annotations

import argparse
import html
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


def load_runs(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
    if not records:
        raise ValueError(f"No runs found in {path}")
    return records


def mean(values: Iterable[float]) -> Optional[float]:
    numbers = list(values)
    return statistics.mean(numbers) if numbers else None


def median(values: Iterable[float]) -> Optional[float]:
    numbers = list(values)
    return statistics.median(numbers) if numbers else None


def ns_to_seconds(value: Any) -> Optional[float]:
    return float(value) / 1_000_000_000 if value is not None else None


def format_number(value: Any, digits: int = 2, suffix: str = "") -> str:
    return "—" if value is None else f"{float(value):.{digits}f}{suffix}"


def format_bytes(value: Any) -> str:
    if value is None:
        return "—"
    size = float(value)
    if size >= 1024**3:
        return f"{size / 1024**3:.2f} GiB"
    return f"{size / 1024**2:.1f} MiB"


def yes_no(value: Any) -> str:
    return "Sim" if value else "Não"


def performance_rows(records: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["model"])].append(record)

    rows: List[Dict[str, Any]] = []
    for model in sorted(grouped):
        model_runs = grouped[model]
        successful = [run for run in model_runs if run.get("status") == "success"]
        usable = [run for run in successful if (run.get("checks") or {}).get("required_structure")]
        strict = [run for run in successful if (run.get("checks") or {}).get("strict_json")]
        length_limited = [
            run
            for run in successful
            if (run.get("ollama_metrics") or {}).get("done_reason") == "length"
        ]

        def performance_values(field: str) -> List[float]:
            return [
                float(run["performance"][field])
                for run in successful
                if (run.get("performance") or {}).get(field) is not None
            ]

        def metric_seconds(field: str) -> List[float]:
            return [
                float(run["ollama_metrics"][field]) / 1_000_000_000
                for run in successful
                if (run.get("ollama_metrics") or {}).get(field) is not None
            ]

        loaded_sizes = [
            float(run["resources"]["ollama_loaded_size_bytes"])
            for run in successful
            if (run.get("resources") or {}).get("ollama_loaded_size_bytes") is not None
        ]
        file_sizes = [
            float(run["model_size_bytes"])
            for run in model_runs
            if run.get("model_size_bytes") is not None
        ]
        rows.append(
            {
                "model": model,
                "runs": len(model_runs),
                "successful_calls": len(successful),
                "usable_outputs": len(usable),
                "strict_json_rate": len(strict) / len(successful) if successful else 0,
                "median_wall_time_seconds": median(performance_values("wall_time_seconds")),
                "median_load_time_seconds": median(metric_seconds("load_duration")),
                "median_prompt_eval_seconds": median(metric_seconds("prompt_eval_duration")),
                "median_generation_seconds": median(metric_seconds("eval_duration")),
                "mean_generation_tokens_per_second": mean(
                    performance_values("generation_tokens_per_second")
                ),
                "length_limit_rate": len(length_limited) / len(successful) if successful else 0,
                "ollama_loaded_size_bytes": max(loaded_sizes) if loaded_sizes else None,
                "model_file_size_bytes": max(file_sizes) if file_sizes else None,
            }
        )
    return rows


def performance_table(rows: Sequence[Mapping[str, Any]]) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f'<th scope="row">{html.escape(str(row["model"]))}</th>'
            f'<td>{row["successful_calls"]}/{row["runs"]}</td>'
            f'<td>{row["usable_outputs"]}/{row["runs"]}</td>'
            f'<td>{format_number(row["strict_json_rate"] * 100, 1, "%")}</td>'
            f'<td>{format_number(row["median_wall_time_seconds"], 2, " s")}</td>'
            f'<td>{format_number(row["median_load_time_seconds"], 2, " s")}</td>'
            f'<td>{format_number(row["median_prompt_eval_seconds"], 2, " s")}</td>'
            f'<td>{format_number(row["median_generation_seconds"], 2, " s")}</td>'
            f'<td>{format_number(row["mean_generation_tokens_per_second"], 2, " tok/s")}</td>'
            f'<td>{format_bytes(row["ollama_loaded_size_bytes"])}</td>'
            f'<td>{format_bytes(row["model_file_size_bytes"])}</td>'
            f'<td>{format_number(row["length_limit_rate"] * 100, 1, "%")}</td>'
            "</tr>"
        )
    return f"""<div class="table-scroll"><table class="summary-table">
<thead><tr>
<th>Modelo</th><th>Chamadas OK</th><th>Outputs válidos</th><th>JSON estrito</th>
<th>Tempo total</th><th>Carregamento</th><th>Prompt</th><th>Geração</th>
<th>Velocidade</th><th>Memória Ollama</th><th>Arquivo</th><th>Truncados</th>
</tr></thead><tbody>{''.join(body)}</tbody></table></div>"""


def output_field(record: Mapping[str, Any], field: str) -> str:
    parsed = record.get("parsed_output") or {}
    if field == "criteria":
        criteria = parsed.get("criteria") or {}
        return str(criteria.get("narrative") or "") if isinstance(criteria, dict) else str(criteria)
    return str(parsed.get(field) or "")


def metric(label: str, value: str) -> str:
    return f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd></div>"


def card(record: Optional[Mapping[str, Any]], model: str) -> str:
    if not record or record.get("status") != "success":
        error = str((record or {}).get("error") or "Execução ausente")
        error_type = str((record or {}).get("error_type") or "Erro")
        return f"""<article class="model-card failed">
<h3>{html.escape(model)}</h3>
<p><strong>{html.escape(error_type)}:</strong> {html.escape(error)}</p>
</article>"""

    title = output_field(record, "badge_name") or "(título ausente)"
    description = output_field(record, "badge_description") or "(descrição ausente)"
    criteria = output_field(record, "criteria") or "(critérios ausentes)"
    checks = record.get("checks") or {}
    metrics = record.get("ollama_metrics") or {}
    performance = record.get("performance") or {}
    resources = record.get("resources") or {}
    model_details = record.get("model_details") or {}
    structure_ok = bool(checks.get("required_structure"))
    warning = "" if structure_ok else '<p class="warning">Saída incompleta ou fora da estrutura esperada.</p>'
    raw_output = ""
    if not structure_ok and record.get("raw_output"):
        raw_output = (
            "<h4>Saída bruta</h4>"
            f'<p class="pre raw">{html.escape(str(record["raw_output"]))}</p>'
        )

    technical_metrics = "".join(
        (
            metric("Tempo observado", format_number(performance.get("wall_time_seconds"), 3, " s")),
            metric("Tempo total Ollama", format_number(ns_to_seconds(metrics.get("total_duration")), 3, " s")),
            metric("Carregamento", format_number(ns_to_seconds(metrics.get("load_duration")), 3, " s")),
            metric("Processamento do prompt", format_number(ns_to_seconds(metrics.get("prompt_eval_duration")), 3, " s")),
            metric("Geração", format_number(ns_to_seconds(metrics.get("eval_duration")), 3, " s")),
            metric("Tokens do prompt", str(metrics.get("prompt_eval_count") or "—")),
            metric("Tokens gerados", str(metrics.get("eval_count") or "—")),
            metric("Velocidade de geração", format_number(performance.get("generation_tokens_per_second"), 2, " tok/s")),
            metric("Velocidade do prompt", format_number(performance.get("prompt_tokens_per_second"), 2, " tok/s")),
            metric("Memória carregada", format_bytes(resources.get("ollama_loaded_size_bytes"))),
            metric("Memória de GPU", format_bytes(resources.get("ollama_size_vram_bytes"))),
            metric("Arquivo do modelo", format_bytes(record.get("model_size_bytes"))),
            metric("Motivo de término", str(metrics.get("done_reason") or "—")),
            metric("JSON estrito", yes_no(checks.get("strict_json"))),
            metric("JSON recuperado", yes_no(checks.get("parser_recovered_json"))),
            metric("Estrutura completa", yes_no(structure_ok)),
        )
    )
    metadata = {
        "modelo": model,
        "digest": record.get("model_digest"),
        "detalhes_modelo": model_details,
        "ollama_version": record.get("ollama_version"),
        "seed": record.get("seed"),
        "parametros": record.get("parameters"),
        "git_commit": record.get("git_commit"),
        "config_sha256": record.get("config_sha256"),
        "input_sha256": record.get("input_sha256"),
        "system_prompt_sha256": record.get("system_prompt_sha256"),
        "prompt_sha256": record.get("prompt_sha256"),
    }
    metadata_text = html.escape(json.dumps(metadata, ensure_ascii=False, indent=2))
    return f"""<article class="model-card">
<h3>{html.escape(model)}</h3>
{warning}
<h4>Título</h4><p>{html.escape(title)}</p>
<h4>Descrição</h4><p class="pre">{html.escape(description)}</p>
<h4>Critérios</h4><p class="pre">{html.escape(criteria)}</p>
{raw_output}
<section class="technical"><h4>Desempenho e recursos desta geração</h4><dl>{technical_metrics}</dl>
<details><summary>Identificação, parâmetros e hashes</summary><pre>{metadata_text}</pre></details></section>
</article>"""


def write_comparison(
    records: Sequence[Mapping[str, Any]],
    summary_rows: Sequence[Mapping[str, Any]],
    path: Path,
) -> None:
    experiment_id = str(records[0]["experiment_id"])
    models = sorted({str(record["model"]) for record in records})
    grouped: Dict[tuple[str, int], Dict[str, Mapping[str, Any]]] = defaultdict(dict)
    case_names: Dict[tuple[str, int], str] = {}
    for record in records:
        key = (str(record["course_id"]), int(record["seed"]))
        grouped[key][str(record["model"])] = record
        case_names[key] = str(record.get("course_name") or record["course_id"])

    sections: List[str] = []
    for course_id, seed in sorted(grouped):
        key = (course_id, seed)
        case_id = f"{course_id}::seed-{seed}"
        case_argument = html.escape(json.dumps(case_id), quote=True)
        cards = "".join(card(grouped[key].get(model), model) for model in models)
        buttons = "".join(
            f'<button type="button" data-model="{html.escape(model)}" '
            f'onclick="chooseWinner({case_argument}, {html.escape(json.dumps(model), quote=True)})">'
            f'{html.escape(model)}</button>'
            for model in models
        )
        sections.append(
            f"""<section class="case" data-case="{html.escape(case_id)}">
<header><h2>{html.escape(course_id)} — {html.escape(case_names[key])}</h2><span>seed {seed}</span></header>
<div class="cards">{cards}</div>
<div class="review"><strong>Qual saída você prefere?</strong>
<div class="choices">{buttons}<button type="button" data-model="Empate" onclick="chooseWinner({case_argument}, 'Empate')">Empate</button></div>
<label>Observações <textarea oninput="saveNote({case_argument}, this.value)" placeholder="Opcional"></textarea></label>
</div></section>"""
        )

    script_config = json.dumps({"experiment_id": experiment_id}, ensure_ascii=False).replace("</", "<\\/")
    document = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Avaliação de modelos — {html.escape(experiment_id)}</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #202124; background: #f4f5f7; }}
body {{ margin: 0 auto; max-width: 1800px; padding: 24px; }} h1 {{ margin-bottom: 4px; }}
.intro {{ max-width: 1000px; color: #555; }} .toolbar {{ position: sticky; top: 0; z-index: 5; padding: 12px 0; background: #f4f5f7ee; }}
button {{ border: 1px solid #777; background: white; border-radius: 7px; padding: 8px 13px; cursor: pointer; }}
button.selected {{ color: white; background: #3157a4; border-color: #3157a4; }}
.table-scroll {{ overflow-x: auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px #00000012; }}
table {{ border-collapse: collapse; width: 100%; white-space: nowrap; }} th, td {{ padding: 10px; border-bottom: 1px solid #ddd; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }} thead th {{ background: #e9eef8; }}
.case {{ margin: 28px 0; padding: 18px; border-radius: 12px; background: white; box-shadow: 0 2px 10px #00000012; }}
.case > header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; }}
.cards {{ display: grid; grid-template-columns: repeat({len(models)}, minmax(360px, 1fr)); gap: 16px; align-items: start; }}
.model-card {{ border: 1px solid #d8dbe2; border-radius: 9px; padding: 15px; min-width: 0; }}
.model-card h3 {{ margin-top: 0; padding-bottom: 8px; border-bottom: 2px solid #3157a4; overflow-wrap: anywhere; }}
.model-card h4 {{ margin-bottom: 5px; }} .pre {{ white-space: pre-wrap; overflow-wrap: anywhere; }} .raw {{ font-family: monospace; }}
.warning, .failed {{ color: #8b1e1e; background: #fff7f7; }}
.technical {{ margin-top: 20px; padding-top: 8px; border-top: 2px solid #dce3f2; }}
.technical dl {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: #d8dbe2; border: 1px solid #d8dbe2; }}
.technical dl div {{ background: #f8f9fb; padding: 8px; }} dt {{ color: #666; font-size: .82rem; }} dd {{ margin: 3px 0 0; font-weight: 650; overflow-wrap: anywhere; }}
details {{ margin-top: 12px; }} details pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #f4f5f7; padding: 10px; }}
.review {{ margin-top: 16px; padding-top: 14px; border-top: 1px solid #ddd; }} .choices {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 12px; }}
textarea {{ display: block; box-sizing: border-box; width: 100%; min-height: 62px; margin-top: 5px; }}
@media (max-width: 900px) {{ .cards {{ grid-template-columns: 1fr; }} .technical dl {{ grid-template-columns: 1fr; }} }}
</style></head><body>
<h1>Avaliação de modelos: {html.escape(experiment_id)}</h1>
<p class="intro">Os modelos, outputs, parâmetros, tempos e recursos estão identificados. O resumo usa medianas para tempos e média para velocidade de geração.</p>
<h2>Resumo técnico</h2>{performance_table(summary_rows)}
<div class="toolbar"><button type="button" onclick="exportReview()">Exportar avaliação JSON</button></div>
{''.join(sections)}
<script>
const reportConfig = {script_config}; const storageKey = `mit-slm-review-open:${{reportConfig.experiment_id}}`;
let reviewState = JSON.parse(localStorage.getItem(storageKey) || '{{}}');
function persist() {{ localStorage.setItem(storageKey, JSON.stringify(reviewState)); }}
function chooseWinner(caseId, model) {{ reviewState[caseId] = reviewState[caseId] || {{}}; reviewState[caseId].winner_model = model; persist(); restoreCase(caseId); }}
function saveNote(caseId, note) {{ reviewState[caseId] = reviewState[caseId] || {{}}; reviewState[caseId].note = note; persist(); }}
function restoreCase(caseId) {{
  const section = document.querySelector(`[data-case="${{CSS.escape(caseId)}}"]`); if (!section) return;
  const state = reviewState[caseId] || {{}};
  section.querySelectorAll('.choices button').forEach(button => button.classList.toggle('selected', button.dataset.model === state.winner_model));
  const textarea = section.querySelector('textarea'); if (textarea && document.activeElement !== textarea) textarea.value = state.note || '';
}}
function exportReview() {{
  const payload = {{experiment_id: reportConfig.experiment_id, exported_at: new Date().toISOString(), choices: reviewState}};
  const blob = new Blob([JSON.stringify(payload, null, 2)], {{type: 'application/json'}}); const link = document.createElement('a');
  link.href = URL.createObjectURL(blob); link.download = `${{reportConfig.experiment_id}}-review.json`; link.click(); URL.revokeObjectURL(link.href);
}}
Object.keys(reviewState).forEach(restoreCase);
</script></body></html>"""
    path.write_text(document, encoding="utf-8")


def generate_reports(results_path: Path) -> None:
    records = load_runs(results_path)
    rows = performance_rows(records)
    result_dir = results_path.parent
    write_comparison(records, rows, result_dir / "comparison.html")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate detailed model comparison reports")
    parser.add_argument("--results", required=True, help="Path to runs.jsonl")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    results_path = Path(args.results).resolve()
    try:
        generate_reports(results_path)
        print(f"Comparação detalhada: {results_path.parent / 'comparison.html'}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"Erro: {exc}") from exc


if __name__ == "__main__":
    main()
