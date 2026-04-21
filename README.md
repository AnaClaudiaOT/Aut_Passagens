# Monitor de passagens para Goiania no Telegram

Este projeto monitora conteudos e ofertas publicas relacionados a passagens para Goiania saindo de:

- `GRU`
- `CGH`
- `VCP`

Ele roda no GitHub Actions todos os dias as `09:00` e `21:00` no horario de Sao Paulo e envia um resumo para o Telegram.

## Como funciona

O monitor consulta paginas publicas de conteudo e promocoes de viagem e procura posts relacionados a Goiania com origem em Sao Paulo ou Campinas.

Em cada execucao, ele envia:

- um resumo dos itens encontrados
- titulo, horario publicado, resumo e link
- uma mensagem de status mesmo quando nada relevante for encontrado

## Requisitos

Voce vai precisar de:

- um bot no Telegram
- um repositorio no GitHub

## Secrets do GitHub

No repositorio, crie estes secrets em `Settings -> Secrets and variables -> Actions`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Estrutura

- [src/flight_monitor.py](./src/flight_monitor.py)
- [.github/workflows/flight-monitor.yml](./.github/workflows/flight-monitor.yml)
- [.env.example](./.env.example)

## Como publicar no GitHub

Crie um repositorio novo e depois, dentro desta pasta, rode:

```bash
git init
git add .
git commit -m "feat: add Goiania flight Telegram monitor"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

## Como testar

1. Configure os secrets.
2. Va em `Actions`.
3. Abra `Goiania Flight Monitor`.
4. Clique em `Run workflow`.

## Observacoes

- O cron do GitHub usa UTC. O horario configurado no workflow corresponde a `09:00` e `21:00` em Sao Paulo.
- O GitHub Actions pode ter pequeno atraso em horarios muito concorridos.
- Esta versao usa fontes publicas e palavras-chave, entao funciona como radar simples de oportunidades e conteudos, nao como buscador oficial de tarifas em tempo real.
- Se as fontes mudarem a estrutura do site, pode ser necessario ajustar o parser.
