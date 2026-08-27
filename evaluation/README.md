# Comparação de modelos

Este diretório executa os mesmos planos de ensino e o mesmo prompt para poucos
modelos Ollama. Ele produz uma comparação visual detalhada e um resumo técnico, sem
envolver geração de imagem ou extração de skills.

## 1. Preparar o ambiente

Crie um ambiente Python. Para executar somente a avaliação, use as dependências
mínimas:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r evaluation/requirements.txt
```

Para também executar a API e o restante do projeto, instale `requirements.txt`
em vez do arquivo mínimo. O ambiente completo está fixado para o Python 3.11
usado no Dockerfile; no Python 3.14, use o arquivo mínimo para o runner e execute
a API pelo Docker.

Inicie somente o Ollama. Não é necessário reiniciar a API entre modelos:

```bash
docker compose up -d ollama
```

## 2. Escolher os modelos

Edite `evaluation/models.yaml` e acrescente as tags exatas:

```yaml
models:
  - name: phi4-mini:3.8b-q4_K_M
  - name: segundo-modelo:tag-exata
  - name: terceiro-modelo:tag-exata
```

Evite `latest` quando existir uma tag versionada. O runner também registra o
digest retornado pelo Ollama.

Para a primeira comparação, mantenha uma seed e `temperature: 0`. Isso torna a
inspeção visual mais estável. Para observar variação posteriormente:

```yaml
generation:
  temperature: 0.1
  seeds: [42, 43, 44]
```

Não deixe estilo, tom, nível ou tipo de critério vazios: a aplicação escolhe
valores aleatórios quando eles não são informados.

## 3. Conferir e executar

Valide a configuração e veja o tamanho da campanha sem chamar modelos:

```bash
python -m evaluation.run --dry-run
```

Faça primeiro um teste com um plano. `--pull` autoriza o runner a baixar os
modelos ausentes:

```bash
python -m evaluation.run --limit 1 --pull
```

Se o teste estiver correto, continue a mesma campanha:

```bash
python -m evaluation.run --resume
```

Cada geração é gravada imediatamente. Se houver interrupção, execute novamente
com `--resume`; somente gerações bem-sucedidas serão ignoradas. Para testar
apenas um dos modelos configurados, use:

```bash
python -m evaluation.run --model phi4-mini:3.8b-q4_K_M --resume
```

Para iniciar uma campanha independente, altere `experiment.id` no YAML. O runner
não sobrescreve uma campanha existente sem `--resume` e recusa misturar uma
configuração alterada com resultados já existentes.

## 4. Avaliar os resultados

Os arquivos ficam em:

```text
evaluation/results/<experiment-id>/
  config.yaml
  runs.jsonl
  comparison.html
```

Abra `comparison.html` no navegador. A página mostra os nomes reais dos modelos,
um resumo comparativo e, junto de cada output, tempos, tokens, velocidade,
memória, formato, parâmetros e identificadores da execução.

Para cada plano, selecione o resultado preferido e, se desejar, escreva uma
observação. As escolhas ficam no armazenamento local do navegador. Ao terminar,
clique em **Exportar avaliação JSON**.

O arquivo `<experiment-id>-review.json` baixado pelo navegador é o artefato
final da revisão. Ele já contém o modelo preferido e as observações de cada
plano; não há uma etapa posterior de sumarização.

## 5. Ler as métricas

As métricas aparecem no `comparison.html`, tanto no resumo por modelo quanto em
cada geração:

- chamadas bem-sucedidas e outputs utilizáveis;
- proporção de JSON estrito;
- mediana do tempo total observado pelo runner;
- média de tokens gerados por segundo;
- tempos medianos de carregamento, processamento do prompt e geração;
- proporção de respostas encerradas pelo limite de tokens;
- tamanho carregado reportado por `GET /api/ps`;
- tamanho do arquivo do modelo reportado por `GET /api/tags`.

O tamanho carregado é a alocação informada pelo Ollama, não o pico total de RAM
do computador. Ele é adequado para comparar o peso relativo dos modelos, mas
não inclui todo o overhead do Docker, do sistema operacional ou da API.

Por padrão há um warm-up descartado para cada modelo, portanto a latência resume
uso aquecido. Para estudar carregamento a frio, crie outra campanha com:

```yaml
ollama:
  warmup: false
  keep_alive: 0
```

Não misture medições quentes e frias na mesma campanha.

## 6. Visualizar o relatório por SSH

Em uma VM acessada por SSH, não é necessário expor uma porta no firewall. Na
VM, execute a partir do repositório, sem `sudo`:

```bash
python3 -m http.server 8765 \
  --bind 127.0.0.1 \
  --directory evaluation/results
```

Mantenha essa sessão aberta. Em outro terminal da sua máquina local, crie o
túnel com sua conta e sua chave SSH:

```bash
ssh -N -T \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:8765:127.0.0.1:8765 \
  usuario@ip-da-vm
```

Abra no navegador local:

```text
http://localhost:8765/badge-models-grounded-v1/comparison.html
```

Tanto o servidor HTTP quanto a porta encaminhada ficam ligados apenas ao
`127.0.0.1`. Não use `--bind 0.0.0.0`, `ssh -g` nem abra a porta 8765 no
firewall. Ao terminar, encerre o túnel e o servidor com `Ctrl+C` nas respectivas
sessões.
## Comandos úteis

Regenerar os relatórios sem executar os modelos novamente:

```bash
python -m evaluation.report \
  --results evaluation/results/badge-models-grounded-v1/runs.jsonl
```

Ver modelos instalados:

```bash
docker exec ollama-service ollama list
```

Ver logs do Ollama:

```bash
docker compose logs -f ollama
```
