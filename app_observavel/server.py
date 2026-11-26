"""Sistema web observavel em 3 fases para o Lab 02 (Aulas 01 a 04)."""

from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
import random
import time

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import Counter, Histogram, MeterProvider, UpDownCounter
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
PORT = int(os.getenv("PORT", "8080"))

SENSITIVE_KEYS = {"cpf", "pan", "cvv", "password", "token", "authorization"}


def safe_log(record: dict) -> dict:
    """Camada 1 de defesa: aplica redacao na origem para chaves criticas."""
    return {
        k: ("[REDACTED]" if k.lower() in SENSITIVE_KEYS else v)
        for k, v in record.items()
    }


def utc_iso_now() -> str:
    """Retorna timestamp UTC ISO-8601 com precisao de milissegundos (NIST SP 800-92)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


resource = Resource.create(
    {
        "service.name": "ci-pipeline",
        "service.instance.id": "sistema-web-01",
        "cicd.pipeline.name": "pagamentos-api",
    }
)

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(endpoint=ENDPOINT, insecure=True),
        schedule_delay_millis=500,
    )
)
trace.set_tracer_provider(tracer_provider)

metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(
        endpoint=ENDPOINT,
        insecure=True,
        preferred_temporality={
            Counter: AggregationTemporality.DELTA,
            Histogram: AggregationTemporality.DELTA,
            UpDownCounter: AggregationTemporality.DELTA,
        },
    ),
    export_interval_millis=1000,
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(
    BatchLogRecordProcessor(
        OTLPLogExporter(endpoint=ENDPOINT, insecure=True),
        schedule_delay_millis=500,
    )
)
set_logger_provider(logger_provider)

otel_logger = logging.getLogger("lab02.app")
otel_logger.setLevel(logging.INFO)
otel_logger.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))

tracer = trace.get_tracer("lab02.sistema")
meter = metrics.get_meter("lab02.sistema")

runs_counter = meter.create_counter("pipeline_runs", description="Total de execucoes")
duration_hist = meter.create_histogram(
    "pipeline_duration_seconds", unit="s", description="Duracao das operacoes"
)
findings_gauge = meter.create_up_down_counter(
    "gate_findings", description="Findings abertos por gate"
)
deploy_counter = meter.create_counter("deploy", description="Total de deploys")


HTML_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Lab 02 — Sistema Observavel em 3 Fases</title>
  <style>
    :root {
      --bg: #0f172a;
      --surface: #ffffff;
      --surface-soft: #f8fafc;
      --text: #181c23;
      --muted: #555f71;
      --blue: #0284c7;
      --teal: #0d9488;
      --green: #2e7d32;
      --red: #901a2e;
      --yellow: #b45309;
      --purple: #6d28d9;
      --border: #e2e8f0;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: #f1f5f9;
      color: var(--text);
      line-height: 1.45;
    }
    header {
      background: var(--bg);
      color: #f8fafc;
      padding: 18px 28px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
      border-bottom: 4px solid var(--teal);
    }
    header h1 { font-size: 20px; font-weight: 700; }
    header p { font-size: 13px; color: #94a3b8; margin-top: 2px; }
    .links { display: flex; flex-wrap: wrap; gap: 8px; }
    .links a {
      text-decoration: none;
      color: #f8fafc;
      background: rgba(255,255,255,0.1);
      border: 1px solid rgba(255,255,255,0.18);
      padding: 6px 12px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
    }
    .links a:hover { background: var(--teal); border-color: var(--teal); }
    main { max-width: 1180px; margin: 22px auto; padding: 0 20px; display: grid; gap: 18px; }
    .tabs { display: flex; gap: 10px; flex-wrap: wrap; }
    .tab-btn {
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      padding: 10px 16px;
      border-radius: 10px;
      font-weight: 700;
      font-size: 13.5px;
      cursor: pointer;
    }
    .tab-btn.active { background: var(--blue); color: #fff; border-color: var(--blue); }
    .phase-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      box-shadow: 0 4px 16px rgba(15,23,42,0.05);
      display: none;
    }
    .phase-card.active { display: block; }
    .phase-card h2 { font-size: 18px; margin-bottom: 6px; color: var(--blue); }
    .phase-desc { font-size: 13.5px; color: var(--muted); margin-bottom: 14px; }
    .btn-row { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
    .action-btn {
      border: none;
      color: #fff;
      padding: 10px 16px;
      border-radius: 9px;
      font-weight: 700;
      font-size: 13px;
      cursor: pointer;
      transition: transform 0.1s ease, opacity 0.15s ease;
    }
    .action-btn:hover { opacity: 0.92; transform: translateY(-1px); }
    .btn-blue { background: var(--blue); }
    .btn-teal { background: var(--teal); }
    .btn-yellow { background: var(--yellow); }
    .btn-red { background: var(--red); }
    .btn-purple { background: var(--purple); }
    .checklist {
      background: var(--surface-soft);
      border-left: 4px solid var(--teal);
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 13px;
    }
    .inspector {
      background: #1e293b;
      color: #e2e8f0;
      border-radius: 14px;
      padding: 18px 20px;
      box-shadow: 0 6px 20px rgba(15,23,42,0.14);
    }
    .inspector h3 { font-size: 15px; color: #38bdf8; margin-bottom: 10px; }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }
    .meta-box {
      background: rgba(255,255,255,0.06);
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 12.5px;
    }
    .meta-box span { display: block; color: #94a3b8; font-size: 11px; text-transform: uppercase; }
    .meta-box code { color: #5eead4; font-family: Consolas, monospace; word-break: break-all; }
    pre {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 12px;
      font-family: Consolas, monospace;
      font-size: 12px;
      overflow-x: auto;
      color: #cbd5e1;
      white-space: pre-wrap;
    }
    .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    @media (max-width: 820px) { .two-col { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Portal da Esteira &amp; Pedidos Observavel (Lab 02)</h1>
      <p>Sistema web instrumentado com OpenTelemetry &rarr; Collector &rarr; Prometheus, Loki, Tempo e Grafana</p>
    </div>
    <nav class="links">
      <a href="http://localhost:3000/d/lab02-sistema" target="_blank">Grafana Dashboard</a>
      <a href="http://localhost:3000/explore" target="_blank">Grafana Explore (Loki / Tempo)</a>
      <a href="http://localhost:9090/query" target="_blank">Prometheus Query</a>
      <a href="http://localhost:9090/alerts" target="_blank">Prometheus Alerts</a>
      <a href="http://localhost:8889/metrics" target="_blank">/metrics (:8889)</a>
    </nav>
  </header>

  <main>
    <div class="tabs">
      <button class="tab-btn active" onclick="showPhase(1, this)">Fase 1 — Revisao Aula 03 (Metricas &amp; Alertas)</button>
      <button class="tab-btn" onclick="showPhase(2, this)">Fase 2 — Aula 04 Parte 1 (Logs JSON, Loki &amp; LGPD)</button>
      <button class="tab-btn" onclick="showPhase(3, this)">Fase 3 — Aula 04 Parte 2 (Correlacao Completa)</button>
    </div>

    <section class="phase-card active" id="phase-1">
      <h2>Fase 1: Metricas, Latencia p95, Exemplars e Alertas</h2>
      <p class="phase-desc">Gere trafego real clicando nos botoes (abra o F12 &rarr; Network para acompanhar cada chamada HTTP) e observe Prometheus + Grafana Dashboard.</p>
      <div class="btn-row">
        <button class="action-btn btn-teal" onclick="callApi('/api/fase1/ok')">1. Executar Pipeline Normal (ok)</button>
        <button class="action-btn btn-blue" onclick="callApi('/api/fase1/slow')">2. Simular Gargalo p95 (slow)</button>
        <button class="action-btn btn-yellow" onclick="callApi('/api/fase1/fail')">3. Disparar Falha SCA (fail)</button>
        <button class="action-btn btn-red" onclick="callApi('/api/fase1/bypass')">4. Deploy Prod sem Gate (bypass)</button>
      </div>
      <div class="checklist">
        <strong>O que validar no Grafana / Prometheus:</strong> rode 2&times; <em>Normal</em>, 1&times; <em>Gargalo</em>, 1&times; <em>Falha</em> e veja o grafico <strong>Latencia p95</strong> com marcador <strong>Exemplar</strong> (clique em <code>Query with Tempo</code>). Depois clique em <em>Deploy sem Gate</em> e confira o alerta <code>DeploySemCoberturaDeGate</code> em <strong>Firing</strong> imediato (<code>for: 0m</code>).
      </div>
    </section>

    <section class="phase-card" id="phase-2">
      <h2>Fase 2: Logging Estruturado (NIST), Loki e Protecao LGPD / PCI-DSS</h2>
      <p class="phase-desc">Compare dados sensiveis enviados na requisicao com o registro estruturado e sanitizado que realmente chega ao Loki e ao Tempo.</p>
      <div class="btn-row">
        <button class="action-btn btn-blue" onclick="callApi('/api/fase2/log-estruturado')">1. Emitir Log JSON Estruturado (NIST UTC)</button>
        <button class="action-btn btn-red" onclick="callApi('/api/fase2/checkout-pii', {cpf:'123.456.789-00', pan:'4532 1111 2222 3333', cvv:'999', email:'ana@empresa.com'})">2. Simular Checkout com CPF, Cartao (PAN) e Token</button>
      </div>
      <div class="checklist">
        <strong>O que validar no Grafana Explore &rarr; Loki:</strong> consulte <code>{service_name="ci-pipeline"} | json</code> e comprove que <code>pan</code>/<code>cvv</code> foram redigidos na origem (<code>[REDACTED]</code>), <code>ci.token</code> e <code>cpf</code> foram apagados pelo <strong>OTel Collector</strong>, <code>user.email</code> virou hash e <code>trace_id</code> ficou preservado fora do indice de labels.
      </div>
    </section>

    <section class="phase-card" id="phase-3">
      <h2>Fase 3: Correlacao Ponta a Ponta (Metrica &harr; Log &harr; Trace)</h2>
      <p class="phase-desc">Dispare um incidente distribuido entre servicos para percorrer o triangulo completo no Grafana sem copiar IDs manualmente.</p>
      <div class="btn-row">
        <button class="action-btn btn-purple" onclick="callApi('/api/fase3/incidente-cadeia')">Simular Incidente em Cadeia (Pedidos &rarr; Pagamento/Gate)</button>
      </div>
      <div class="checklist">
        <strong>Navegacao bidirecional no Grafana:</strong> 1) Abra o trace pelo <strong>Exemplar</strong> ou pelo <strong>Loki</strong> clicando no botao <strong>Ver Trace no Tempo</strong> (<em>Derived Fields</em>). 2) Dentro do span vermelho <code>gate.pagamento-sca</code>, clique em <strong>Logs for this span</strong> (<em>Trace to Logs</em>) para voltar aos logs exatos desse <code>trace_id</code>.
      </div>
    </section>

    <section class="inspector">
      <h3>Inspector de Rede &amp; Telemetria (Ultima Chamada HTTP)</h3>
      <div class="meta-grid">
        <div class="meta-box"><span>Endpoint &amp; Status</span><code id="metaStatus">Aguardando acao...</code></div>
        <div class="meta-box"><span>Latencia HTTP</span><code id="metaLatency">-</code></div>
        <div class="meta-box"><span>Header traceparent</span><code id="metaTraceparent">-</code></div>
        <div class="meta-box"><span>trace_id (Correlacao)</span><code id="metaTraceId">-</code></div>
      </div>
      <div class="two-col">
        <div>
          <p style="font-size:12px; color:#94a3b8; margin-bottom:6px;">Payload de Entrada / Resposta da API</p>
          <pre id="rawOutput">{}</pre>
        </div>
        <div>
          <p style="font-size:12px; color:#94a3b8; margin-bottom:6px;">Log JSON Estruturado &amp; Consulta LogQL Sugerida</p>
          <pre id="logOutput">{}</pre>
        </div>
      </div>
    </section>
  </main>

  <script>
    function showPhase(num, btn) {
      document.querySelectorAll('.phase-card').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById('phase-' + num).classList.add('active');
      btn.classList.add('active');
    }

    async function callApi(path, body = null) {
      const started = performance.now();
      const opts = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : '{}'
      };
      const resp = await fetch(path, opts);
      const elapsed = Math.round(performance.now() - started);
      const data = await resp.json();

      document.getElementById('metaStatus').textContent = `POST ${path} -> HTTP ${resp.status}`;
      document.getElementById('metaLatency').textContent = `${elapsed} ms`;
      document.getElementById('metaTraceparent').textContent = resp.headers.get('traceparent') || data.traceparent || '-';
      document.getElementById('metaTraceId').textContent = resp.headers.get('X-Trace-Id') || data.trace_id || '-';

      document.getElementById('rawOutput').textContent = JSON.stringify({
        request_payload: body || {},
        api_response: data
      }, null, 2);

      const tid = data.trace_id || '';
      document.getElementById('logOutput').textContent = JSON.stringify({
        emitted_json_log: data.log_preview || {},
        logql_query: `{service_name="ci-pipeline"} |= "${tid}"`
      }, null, 2);
    }
  </script>
</body>
</html>
"""


def emit_json_log(
    level_name: str,
    event_name: str,
    message: str,
    trace_id_hex: str,
    span_id_hex: str,
    gate: str = "none",
    channel: str = "app",
    extra_attrs: dict | None = None,
) -> dict:
    """Emite log estruturado JSON no padrao NIST SP 800-92 com contexto do span ativo."""
    payload = {
        "timestamp": utc_iso_now(),
        "level": level_name,
        "service": "ci-pipeline",
        "channel": channel,
        "event": event_name,
        "gate": gate,
        "trace_id": trace_id_hex,
        "span_id": span_id_hex,
        "message": message,
    }
    attrs = {"channel": channel, "event": event_name, "gate": gate, "trace_id": trace_id_hex}
    if extra_attrs:
        attrs.update(extra_attrs)

    log_line = json.dumps(payload, ensure_ascii=False)
    if level_name == "ERROR":
        otel_logger.error(log_line, extra=attrs)
    elif level_name == "WARN":
        otel_logger.warning(log_line, extra=attrs)
    else:
        otel_logger.info(log_line, extra=attrs)
    return payload


class ObservavelHandler(BaseHTTPRequestHandler):
    """Servidor HTTP do portal observavel com rotas didaticas em 3 fases."""

    def log_message(self, format: str, *args) -> None:
        return

    def _send_html(self, content: str) -> None:
        encoded = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, status: int, body: dict, traceparent: str, trace_id_hex: str) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("traceparent", traceparent)
        self.send_header("X-Trace-Id", trace_id_hex)
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            self._send_html(HTML_PAGE)
            return
        if self.path == "/health":
            self._send_json(200, {"status": "ok"}, "-", "-")
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Rota nao encontrada")

    def do_POST(self) -> None:
        req_body = self._read_json_body()
        run_id = f"run-{random.randint(1000, 9999)}"
        started = time.monotonic()

        if self.path in ("/api/fase1/ok", "/api/fase1/slow", "/api/fase1/fail", "/api/fase1/bypass"):
            mode = self.path.rsplit("/", 1)[-1]
            with tracer.start_as_current_span("pipeline.run") as root_span:
                ctx = root_span.get_span_context()
                trace_id_hex = format(ctx.trace_id, "032x")
                span_id_hex = format(ctx.span_id, "016x")
                traceparent = f"00-{trace_id_hex}-{span_id_hex}-01"
                root_span.set_attribute("ci.pipeline.id", run_id)
                root_span.set_attribute("vcs.ref.head.name", "main")
                root_span.set_attribute("ci.token", "ghp_segredo_lab02")
                root_span.set_attribute("user.email", "ana@empresa.com")

                if mode != "bypass":
                    with tracer.start_as_current_span("sast-scan") as sast_span:
                        sast_span.set_attribute("gate.name", "sast")
                        time.sleep(0.1)
                        sast_span.set_attribute("gate.result", "pass")
                    with tracer.start_as_current_span("sca-scan") as sca_span:
                        sca_span.set_attribute("gate.name", "sca")
                        time.sleep(0.95 if mode == "slow" else (0.35 if mode == "fail" else 0.12))
                        if mode == "fail":
                            sca_span.set_attribute("gate.result", "fail")
                            sca_span.set_attribute("gate.findings.critical", 2)
                            sca_span.add_event("gate.failed", {"reason": "CVE critico"})
                            sca_span.set_status(Status(StatusCode.ERROR))
                            root_span.set_status(Status(StatusCode.ERROR))
                        else:
                            sca_span.set_attribute("gate.result", "pass")

                if mode != "fail":
                    with tracer.start_as_current_span("deploy-prod") as dep_span:
                        dep_span.set_attribute("deploy.env", "prod")
                        time.sleep(0.08)

                elapsed = round(time.monotonic() - started, 3)
                status_label = "failed" if mode == "fail" else "success"
                runs_counter.add(1, {"branch": "main", "status": status_label})
                duration_hist.record(elapsed, {"branch": "main"})
                findings_gauge.add(2 if mode == "fail" else 0, {"gate": "sca", "severity": "critical"})
                if mode != "fail":
                    deploy_counter.add(
                        1,
                        {
                            "env": "prod",
                            "result": "success",
                            "gate_executed": "false" if mode == "bypass" else "true",
                        },
                    )

                log_preview = emit_json_log(
                    "ERROR" if mode == "fail" else ("WARN" if mode == "bypass" else "INFO"),
                    f"pipeline.{mode}",
                    f"Execucao {run_id} concluida em modo {mode} ({elapsed}s)",
                    trace_id_hex,
                    span_id_hex,
                    gate="sca" if mode != "bypass" else "none",
                    channel="audit" if mode == "bypass" else "app",
                )
                http_code = 500 if mode == "fail" else 200
                self._send_json(
                    http_code,
                    {
                        "run_id": run_id,
                        "mode": mode,
                        "status": status_label,
                        "duration_s": elapsed,
                        "trace_id": trace_id_hex,
                        "traceparent": traceparent,
                        "log_preview": log_preview,
                    },
                    traceparent,
                    trace_id_hex,
                )
            return

        if self.path in ("/api/fase2/log-estruturado", "/api/fase2/checkout-pii"):
            is_pii = self.path.endswith("checkout-pii")
            with tracer.start_as_current_span("fase2.logging") as root_span:
                ctx = root_span.get_span_context()
                trace_id_hex = format(ctx.trace_id, "032x")
                span_id_hex = format(ctx.span_id, "016x")
                traceparent = f"00-{trace_id_hex}-{span_id_hex}-01"

                raw_record = {
                    "cpf": req_body.get("cpf", "123.456.789-00"),
                    "pan": req_body.get("pan", "4532 1111 2222 3333"),
                    "cvv": req_body.get("cvv", "999"),
                    "email": req_body.get("email", "ana@empresa.com"),
                    "order_id": run_id,
                }
                app_record = {
                    "order_id": run_id,
                    "pan": raw_record["pan"],
                    "cvv": raw_record["cvv"],
                }
                sanitized_app = safe_log(app_record) if is_pii else {"order_id": run_id}
                root_span.set_attribute("ci.token", "ghp_segredo_lab02")
                if is_pii:
                    root_span.set_attribute("cpf", raw_record["cpf"])
                    root_span.set_attribute("pan", raw_record["pan"])
                    root_span.set_attribute("user.email", raw_record["email"])

                log_preview = emit_json_log(
                    "INFO",
                    "checkout.audit" if is_pii else "pipeline.structured_log",
                    f"Registro seguro ({json.dumps(sanitized_app, ensure_ascii=False)})",
                    trace_id_hex,
                    span_id_hex,
                    gate="compliance" if is_pii else "sast",
                    channel="audit" if is_pii else "app",
                    extra_attrs={
                        "ci.token": "ghp_segredo_lab02",
                        "cpf": raw_record["cpf"] if is_pii else "none",
                        "pan": raw_record["pan"] if is_pii else "none",
                        "user.email": raw_record["email"],
                    },
                )
                self._send_json(
                    200,
                    {
                        "status": "logged",
                        "camada_1_app_safe_log": sanitized_app,
                        "camada_2_collector_scrub": "ci.token e cpf deletados; user.email em hash",
                        "trace_id": trace_id_hex,
                        "traceparent": traceparent,
                        "log_preview": log_preview,
                    },
                    traceparent,
                    trace_id_hex,
                )
            return

        if self.path == "/api/fase3/incidente-cadeia":
            with tracer.start_as_current_span("http.post /api/fase3/incidente-cadeia") as root_span:
                ctx = root_span.get_span_context()
                trace_id_hex = format(ctx.trace_id, "032x")
                span_id_hex = format(ctx.span_id, "016x")
                traceparent = f"00-{trace_id_hex}-{span_id_hex}-01"

                emit_json_log(
                    "INFO",
                    "checkout.started",
                    f"Requisicao {run_id} recebida no gateway HTTP",
                    trace_id_hex,
                    span_id_hex,
                    gate="gateway",
                )

                with tracer.start_as_current_span("service.pedidos") as pedidos_span:
                    p_span_hex = format(pedidos_span.get_span_context().span_id, "016x")
                    time.sleep(0.15)
                    emit_json_log(
                        "WARN",
                        "payment.retry",
                        "Timeout parcial ao validar gate de pagamento; tentando novamente",
                        trace_id_hex,
                        p_span_hex,
                        gate="pagamento",
                    )

                    with tracer.start_as_current_span("gate.pagamento-sca") as pay_span:
                        pay_span_hex = format(pay_span.get_span_context().span_id, "016x")
                        time.sleep(0.35)
                        pay_span.set_attribute("gate.name", "pagamento-sca")
                        pay_span.set_attribute("gate.findings.critical", 1)
                        pay_span.add_event("gate.failed", {"reason": "Dependencia bloqueada em transacao"})
                        pay_span.set_status(Status(StatusCode.ERROR))
                        pedidos_span.set_status(Status(StatusCode.ERROR))
                        root_span.set_status(Status(StatusCode.ERROR))

                        log_err = emit_json_log(
                            "ERROR",
                            "gate.failed",
                            "Falha critica na cadeia Pedidos -> gate.pagamento-sca",
                            trace_id_hex,
                            pay_span_hex,
                            gate="pagamento-sca",
                        )

                elapsed = round(time.monotonic() - started, 3)
                runs_counter.add(1, {"branch": "main", "status": "failed"})
                duration_hist.record(elapsed, {"branch": "main"})
                findings_gauge.add(1, {"gate": "sca", "severity": "critical"})

                self._send_json(
                    500,
                    {
                        "run_id": run_id,
                        "status": "error",
                        "duration_s": elapsed,
                        "trace_id": trace_id_hex,
                        "traceparent": traceparent,
                        "log_preview": log_err,
                    },
                    traceparent,
                    trace_id_hex,
                )
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint nao encontrado")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), ObservavelHandler)
    print(f"[app-observavel] Servidor ouvindo em http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    finally:
        logger_provider.shutdown()
        meter_provider.shutdown()
        tracer_provider.shutdown()
