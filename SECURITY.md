# Política de Segurança

## Garantias de segurança do projeto

O ServiceNow Knowledge Builder nunca automatiza ações de negócio do
ServiceNow, nunca preenche formulários, nunca clica em nome do
usuário, e nunca automatiza ou armazena credenciais, códigos MFA ou
tokens do Microsoft Entra ID (SSO). A autenticação é sempre manual.
Ver `RS-001` a `RS-015` no documento de Regras de Negócio (fonte da
verdade — ver [README.md](README.md)) para a lista completa de
garantias.

## Versões suportadas

Enquanto o projeto estiver em `0.x` (ver [VERSION](VERSION) /
[CHANGELOG.md](CHANGELOG.md)), apenas a versão mais recente publicada
recebe correções de segurança.

## Reportando uma vulnerabilidade

Se você identificar uma vulnerabilidade de segurança — incluindo
qualquer comportamento que viole as garantias acima (ex.: captura ou
persistência de credenciais/MFA, preenchimento automático de campos de
login, ou qualquer automação de ações de negócio do ServiceNow) —
reporte de forma privada, sem abrir uma issue pública:

- **E-mail:** crystianemello@gmail.com

Inclua, se possível: versão afetada, passos para reproduzir, e o
impacto observado. Como este é um projeto mantido por uma única
pessoa, não há SLA formal de resposta, mas relatos de segurança têm
prioridade sobre outras demandas.

## Escopo

Este projeto é uma ferramenta de observação read-only de sessões já
autenticadas do ServiceNow. Vulnerabilidades em dependências de
terceiros (Playwright, Pydantic, etc.) devem ser reportadas também aos
mantenedores dessas dependências, além de nos avisar aqui caso afetem
este projeto diretamente.
