# OXYN Command SaaS — hardening do baseline (2026-07-11)

## Contexto

O projeto foi copiado de `OXYN-Command-SaaS-Python-v0.1.0` (Windows) para
`/home/caiogoes/oxyn` como baseline (commit `9ade914`). É um backend FastAPI
multi-tenant para gestão operacional de anestesiologia: auth JWT, hospitais/salas,
escalas, checklist de segurança, alertas, auditoria e painel. ~1100 linhas,
código limpo, sem nenhuma migração Alembic gerada ainda.

Esta rodada foca em **consolidar o que já existe** — não em construir os itens
da lista "próxima evolução" do README (billing, WebSockets/Redis, integrações
externas, painel admin). Esses ficam fora de escopo por YAGNI.

## Escopo

### 1. Segurança de autenticação

- `User` ganha três colunas:
  - `failed_login_attempts: int` (default 0)
  - `locked_until: datetime | None`
  - `token_version: int` (default 0)
- Login errado incrementa `failed_login_attempts`; ao atingir 5, seta
  `locked_until = now + 15min` e passa a rejeitar login (mesmo com senha certa)
  até o horário passar, retornando 423 com mensagem genérica.
- Login certo reseta `failed_login_attempts` para 0.
- `token_version` é embutido no payload do JWT (`tv`). `decode_token`/
  `get_current_user` passam a exigir que `tv` do token bata com o
  `token_version` atual do usuário no banco — senão, 401.
- Novo endpoint `POST /api/v1/auth/logout` (autenticado): incrementa
  `token_version`, invalidando instantaneamente todo access/refresh token
  emitido antes. Não precisa de tabela de sessões nem de Redis.
- Rate limit simples por IP em `/auth/login`: contador em memória (janela
  deslizante, sem dependência nova). Limitação conhecida: só funciona em
  processo único; quando o deploy for multi-worker/multi-instância, substituir
  por um backend compartilhado (Redis), como o próprio README já prevê.

### 2. Erros e validação

- `app/errors.py` novo: handlers globais para `RequestValidationError` (422
  com lista estruturada de erros por campo) e `Exception` não tratada (500
  genérico ao cliente + log completo com traceback no servidor).
- `ShiftCreate` ganha `model_validator` garantindo `ends_at > starts_at`
  (hoje essa checagem só existe dentro do router `create_shift`).
- `resolve_alert` passa a rejeitar (409) alerta já resolvido, em vez de
  sobrescrever `resolved_at`/`resolved_by_id` silenciosamente.
- Transições de status de sala (`OperatingRoom.status`) passam a ser
  validadas contra uma máquina de estados simples:
  `free → preparation → surgery → recovery → free`, e `blocked` acessível de
  qualquer estado (para manutenção/interdição). Transição fora dessa lista
  retorna 409.

### 3. Cobertura de testes

Expandir `tests/test_api.py` cobrindo:
- Permissão por role (ex.: `viewer`/`nurse` não conseguem criar hospital).
- Isolamento entre tenants (objeto de outro tenant retorna 404).
- Lockout após 5 tentativas de login erradas e liberação após o tempo.
- Logout invalida token anterior (chamada subsequente com o token antigo
  falha com 401).
- Validação de `ShiftCreate` (fim antes do início → 422).
- Dupla resolução de alerta → 409.
- Transição inválida de status de sala → 409.

### 4. Observabilidade

- Middleware que gera um `request_id` (uuid4) por requisição, expõe no
  header de resposta `X-Request-ID` e injeta num `contextvar` usado por um
  `logging.Filter` para aparecer em todo log daquela requisição.
- Logging estruturado básico via `logging` da stdlib (formatter simples com
  timestamp, nível, request_id, mensagem) — sem dependência nova.
- Eventos logados: login (sucesso/falha/lockout), logout, exceção não
  tratada (com traceback).

### 5. Migração Alembic

Não existe nenhuma migração no repositório (pasta `alembic/versions` vazia,
só `.gitkeep`). Vou gerar a primeira migração via `alembic revision
--autogenerate` já refletindo o schema completo (incluindo as três colunas
novas de auth), tornando-a a forma oficial de subir o schema — o
`scripts.bootstrap` deixa de usar `create_all` e passa a assumir que
`alembic upgrade head` já rodou.

## Fora de escopo (adiado)

Billing/cobrança recorrente, WebSockets/Redis para tempo real, integrações
externas (DoctorID, WhatsApp), painel administrativo da plataforma, MFA,
refactor para camada de serviço separada dos routers. Nenhum desses tem
demanda concreta ainda e o código atual é pequeno o suficiente para não
precisar de uma camada de serviço separada agora.

## Fora de escopo — não alterado

Estrutura de diretórios, Docker/Docker Compose, dependências principais
(FastAPI/SQLAlchemy/Alembic/JWT/Argon2), rotas e nomes de endpoints
existentes, modelo de dados de hospitais/escalas/checklist/alertas fora dos
pontos listados acima.
