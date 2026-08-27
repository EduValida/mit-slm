# Deploy para avaliação de modelos

O Compose usa uma imagem oficial e versionada do Ollama. O modelo selecionado é
baixado automaticamente e armazenado no volume persistente `ollama-data`.

## Configuração

```bash
cp .env.example .env
```

As principais variáveis são:

```env
OLLAMA_VERSION=0.32.13
MODEL_NAME=phi4-mini:3.8b-q4_K_M
MODEL_TEMPERATURE=0.10
MODEL_TOP_P=0.9
MODEL_TOP_K=25
MODEL_NUM_PREDICT=1024
MODEL_REPEAT_PENALTY=1.05
MODEL_NUM_CTX=6144
MODEL_SEED=
MODEL_KEEP_ALIVE=30m
```

O system prompt compartilhado está em
`app/prompts/badge_system_prompt.txt` e é enviado pela aplicação para todos os
modelos.

## Execução

```bash
./start.sh --build
```

Para trocar o modelo, altere `MODEL_NAME` no `.env` e execute:

```bash
docker compose up -d
```

O serviço `model-loader` baixa o modelo antes de iniciar a API. O comando
`docker compose down` preserva os modelos; `docker compose down -v` remove o
volume e força um novo download.

## Comparação estruturada

Para executar vários modelos sobre os planos em `data/structured`, coletar
métricas e gerar uma comparação visual detalhada, consulte
[`evaluation/README.md`](../evaluation/README.md). O runner se comunica
diretamente com o Ollama e não exige reiniciar a API entre modelos.
