# Lab 02 — Sistema Observável em 3 Fases (Aulas 01 a 04)

Neste laboratório você vai subir uma aplicação web instrumentada em **Docker** conectada à stack completa de observabilidade (**OpenTelemetry Collector**, **Prometheus**, **Grafana Loki**, **Grafana Tempo** e **Grafana**), sem instalar nada fora do Docker.

---

## Pré-requisito único

- **Docker** com **Docker Compose** (`docker compose version`).
- *(Se o Lab 01 ainda estiver rodando, encerre antes com `docker compose down -v` na pasta do Lab 01 para liberar as portas.)*

---

## Passo 0 — Subir e verificar a infraestrutura

Abra o terminal nesta pasta (`lab_02_sistema_observavel/`) e execute:

```bash
docker compose up -d --build
```

Confirme que todos os 6 serviços estão de pé (`running`):

```bash
docker compose ps
```

| Serviço | URL / Porta | Papel no Laboratório |
| :--- | :--- | :--- |
| **Portal da Esteira & Pedidos** (`app-observavel`) | `http://localhost:8080` | Sistema web com botões para disparar as 3 Fases via chamadas HTTP reais |
| **Grafana** | `http://localhost:3000` | Dashboards + Explore (**Loki**, **Tempo** e **Prometheus** já configurados) |
| **Prometheus** | `http://localhost:9090` | Tela **Query** (`Table` / `Graph`), **Status → Targets** e **Alerts** |
| **OTel Collector (`/metrics`)** | `http://localhost:8889/metrics` | Métricas acumuladas em formato OpenMetrics raspadas pelo Prometheus |
| **Loki API** | `http://localhost:3100` | Armazenamento centralizado de logs (recebe OTLP em `/otlp`) |
| **Tempo API** | `http://localhost:3200` | Armazenamento distribuído de traces |

Verifique rapidamente em [http://localhost:9090/targets](http://localhost:9090/targets) se o alvo `otel-collector:8889` aparece com estado **`UP`**.

---

## Fase 1 — Revisão da Aula 03 (Métricas, `p95`, Exemplars e Alertas)

1. **Abra o portal e o DevTools do navegador:**
   - Acesse `http://localhost:8080` (já abre na aba **Fase 1**).
   - Pressione `F12` no navegador e clique na aba **Network** (Rede) para acompanhar cada chamada HTTP enviada ao backend Python.
2. **Gere execuções reais pelos botões:**
   - Clique **2 vezes** em **`1. Executar Pipeline Normal (ok)`**.
   - Clique **1 vez** em **`2. Simular Gargalo p95 (slow)`** *(simula lentidão acima de 1 segundo)*.
   - Clique **1 vez** em **`3. Disparar Falha SCA (fail)`** *(retorna HTTP `500`)*.
3. **Inspecione rede e contexto distribuído:**
   - Na aba **Network (`F12`)**, clique em uma chamada (ex.: `fail`) → aba **Headers** → **Response Headers**: veja os cabeçalhos **`traceparent`** e **`X-Trace-Id`**.
   - No quadro escuro **Inspector de Rede & Telemetria** (abaixo dos botões), confirme `Endpoint & Status`, `Latencia HTTP` e `trace_id`.
4. **Consulte métricas no Prometheus 3 (`http://localhost:9090/query`):**
   - *(No Prometheus 3, a página inicial já é **Query**. Abaixo da caixa **Expression**, alterne entre **Table** para valor atual nos últimos 5 minutos e **Graph** para a linha no tempo.)*
   - Teste uma consulta por vez e clique em **Execute**:
     ```promql
     pipeline_runs_total
     ```
     ```promql
     sum(pipeline_runs_total{status="failed"}) / sum(pipeline_runs_total)
     ```
     ```promql
     histogram_quantile(0.95, sum(rate(pipeline_duration_seconds_bucket[5m])) by (le))
     ```
     ```promql
     sum(gate_findings) by (gate, severity)
     ```
5. **Abra o Dashboard e use Exemplars no Grafana (`http://localhost:3000/d/lab02-sistema`):**
   - Confira no canto superior direito se o intervalo está em **`Last 15 minutes`**.
   - Observe os painéis **`Execucoes Registradas`**, **`Deploys em Prod com Gate (%)`** (em `100%`) e **`Findings Criticos por Gate`**.
   - No gráfico **`Latencia p95 (com Exemplars)`**, passe o mouse sobre uma estrela/diamante do **Exemplar** para ver `trace_id` e clique no botão **`Query with Tempo`** dentro do card para abrir o trace exato no **Tempo**.
6. **Teste alerta operacional × compliance (`http://localhost:9090/alerts`):**
   - Volte em `http://localhost:8080` (aba **Fase 1**) e clique em **`4. Deploy Prod sem Gate (bypass)`**.
   - Aguarde ~5–10 segundos e acesse `http://localhost:9090/alerts`:
     - **`AltaTaxaDeFalhaPipeline`** usa `for: 1m` (entra em **Pending** amarelo e vai para **Firing** vermelho após sustentar 1 minuto).
     - **`DeploySemCoberturaDeGate`** vai direto para **`Firing`** imediato (`for: 0m`) por ser violação de compliance em produção.
     - *(Lembrete: a UI do Prometheus é somente leitura para regras; a definição fica em `config/alert.rules.yaml`.)*

---

## Fase 2 — Aula 04 Parte 1 (Logs JSON, Loki e Proteção LGPD / PCI-DSS)

1. Em `http://localhost:8080`, clique na aba **`Fase 2 — Aula 04 Parte 1`**.
2. **Validar estrutura NIST SP 800-92:**
   - Clique em **`1. Emitir Log JSON Estruturado (NIST UTC)`**.
   - No **Inspector**, confira o JSON emitido com `timestamp` em UTC ISO-8601 (terminando em `Z`), `level`, `service`, `channel`, `event`, `gate`, `trace_id`, `span_id` e `message`.
3. **Validar Defesa em Camadas (LGPD & PCI-DSS):**
   - Clique em **`2. Simular Checkout com CPF, Cartao (PAN) e Token`**.
   - No **Inspector** (`Payload de Entrada / Resposta da API`), compare o `request_payload` bruto (`cpf`, `pan`, `cvv`, `email`) com `camada_1_app_safe_log`: `pan` e `cvv` já saíram censurados na origem como **`[REDACTED]`**.
4. **Consultar no Grafana → Explore (`http://localhost:3000/explore`):**
   - No topo esquerdo, selecione o datasource **`Loki`**.
   - No canto direito da caixa de consulta, mude de *Builder* para **`Code`**.
   - Execute cada consulta LogQL abaixo e clique em **Run query**:
     ```logql
     {service_name="ci-pipeline"} | json
     ```
     ```logql
     {service_name="ci-pipeline"} | json | channel="audit"
     ```
     ```logql
     sum by (gate) (count_over_time({service_name="ci-pipeline"} | json [5m]))
     ```
   - **Expandir e comprovar proteção + baixa cardinalidade:** clique na seta (`>`) ao lado da linha de log do checkout e confira:
     - **Camada 1 (Aplicação):** `pan` e `cvv` chegam como `[REDACTED]`.
     - **Camada 2 (OTel Collector `attributes/scrub`):** `ci.token` e `cpf` **não existem** (removidos por `action: delete`) e `user_email` aparece como um **hash SHA-256** (`action: hash`).
     - **Baixa Cardinalidade:** os únicos *Stream labels* indexados no Loki são `service_name` e `service_instance_id`, enquanto `trace_id` permanece consultável fora do índice de labels.

---

## Fase 3 — Aula 04 Parte 2 (Correlação Completa: Métrica ↔ Log ↔ Trace)

1. Em `http://localhost:8080`, clique na aba **`Fase 3 — Aula 04 Parte 2`**.
2. Clique em **`Simular Incidente em Cadeia (Pedidos → Pagamento/Gate)`**.
   - Na aba **Network (`F12`)**, confirme o retorno **HTTP `500`** com `traceparent` e `X-Trace-Id`.
   - No **Inspector**, copie o `trace_id` ou a consulta `logql_query` sugerida (`{service_name="ci-pipeline"} |= "<trace_id>"`).
3. **Percorra o triângulo completo no Grafana (`http://localhost:3000`):**
   - **Caminho A (Log → Trace via `Derived Fields`):**
     1. Abra **Explore → Loki** (modo **`Code`**) e execute `{service_name="ci-pipeline"} |= "<trace_id>"`.
     2. Expanda a linha `ERROR` (`gate.failed`).
     3. Ao lado do campo `trace_id`, clique no botão **`Ver Trace no Tempo`**.
   - **Caminho B (Trace → Log via `Trace to Logs`):**
     1. Já dentro do **Tempo**, inspecione a árvore de 3 spans (`http.post /api/fase3/incidente-cadeia` → `service.pedidos` → `gate.pagamento-sca` em vermelho com evento `gate.failed`).
     2. No span `gate.pagamento-sca`, clique no ícone/botão **`Logs for this span`** para abrir automaticamente no **Loki** os 3 logs correlacionados (`INFO checkout.started`, `WARN payment.retry`, `ERROR gate.failed`).
   - **Caminho C (Métrica → Trace via `Exemplar`):**
     1. No dashboard **`Sistema Observavel — Lab 02`**, passe o mouse sobre uma estrela no gráfico `Latencia p95 (com Exemplars)` e clique em **`Query with Tempo`**.

---

## Encerramento e limpeza

Ao finalizar o laboratório, pare e remova os containers e volumes para que contadores, logs e traces comecem zerados na próxima execução:

```bash
docker compose down -v
```
