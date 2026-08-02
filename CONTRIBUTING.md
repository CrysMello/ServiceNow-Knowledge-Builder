# Contribuindo

O ServiceNow Knowledge Builder é um projeto de código fechado, criado,
arquitetado e mantido por [Crystiane Mello](AUTHORS.md). Toda
contribuição — interna ou externa — passa por revisão e aprovação da
mantenedora antes de ser integrada.

## Antes de propor uma mudança

A implementação deste projeto é sempre rastreável a uma hierarquia de
documentos-fonte (ver "Fonte da verdade" no [README](README.md)):
Product Vision, SRS, Business Rules, SAD, Module Specifications,
Interface Contracts e AI Coding Standards. Qualquer mudança de
comportamento, arquitetura ou contrato deve ser compatível com esses
documentos — divergências devem ser discutidas com a mantenedora antes
da implementação.

## Ambiente de desenvolvimento

```bash
python -m venv .venv
. .venv/Scripts/activate        # Windows
pip install -e ".[dev]"
playwright install chromium
```

## Antes de abrir um Pull Request

Rode a suíte de verificação completa e garanta que tudo passa:

```bash
pytest
ruff check .
black --check .
mypy src
```

## Estilo e convenções

- Siga as convenções já usadas no código (Clean Architecture em quatro
  camadas — ver [docs/architecture/README.md](docs/architecture/README.md)).
- Não introduza automação de ações de negócio do ServiceNow nem
  qualquer forma de captura/armazenamento de credenciais ou tokens de
  MFA/SSO — essas são garantias de segurança centrais do projeto
  (RS-001 a RS-015).
- Mensagens de commit devem ser descritivas e em português, seguindo o
  histórico existente do repositório.

## Modelo de desenvolvimento

Este projeto segue o modelo **Human-directed AI development**:
ferramentas de IA podem ser usadas como apoio à implementação, mas
toda decisão de arquitetura, engenharia e produto é humana — da
mantenedora. Contribuições geradas com apoio de IA são bem-vindas,
desde que revisadas e compreendidas por quem as propõe.

## Dúvidas ou propostas

Abra uma issue no repositório ou entre em contato com a mantenedora
(ver [SECURITY.md](SECURITY.md) para o canal de contato).
