# Monitor de passagens para Goiania no Telegram

Este projeto consulta tarifas para `GYN` saindo de:

- `GRU`
- `CGH`
- `VCP`

Ele roda no GitHub Actions todos os dias as `09:00` e `21:00` no horario de Sao Paulo e envia um resumo para o Telegram.

## Como funciona

O monitor usa a API oficial da Amadeus para buscar as menores tarifas de ida e volta nos proximos 90 dias, com estadia entre 2 e 7 dias.

Em cada execucao, ele envia:

- a melhor tarifa geral encontrada
- as melhores tarifas por aeroporto de origem
- um destaque quando o preco ficar abaixo do limite configurado

## Requisitos

Voce vai precisar de:

- um bot no Telegram
- um repositorio no GitHub
- uma conta no Amadeus for Developers

## Criando as credenciais da Amadeus

1. Acesse [Amadeus for Developers](https://developers.amadeus.com/).
2. Crie uma conta.
3. Crie uma nova aplicacao.
4. Copie o `API Key` e o `API Secret`.

Esses valores serao usados como:

- `AMADEUS_CLIENT_ID`
- `AMADEUS_CLIENT_SECRET`

O projeto usa por padrao o ambiente `test`. Se voce quiser usar producao, configure `AMADEUS_ENV=production`.

## Secrets do GitHub

No repositorio, crie estes secrets em `Settings -> Secrets and variables -> Actions`:

- `AMADEUS_CLIENT_ID`
- `AMADEUS_CLIENT_SECRET`
- `AMADEUS_ENV`
- `DEAL_THRESHOLD_BRL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Valores sugeridos:

- `AMADEUS_ENV`: `test`
- `DEAL_THRESHOLD_BRL`: `550`

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
- O ambiente `test` da Amadeus usa dados de cache, entao os valores sao bons para monitoramento, mas nao substituem validacao final no site da companhia ou agregador.
