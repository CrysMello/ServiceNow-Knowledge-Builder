# Exemplos

Reservado para pequenos exemplos de uso executáveis, à medida que os
módulos existam (AI Coding Standards, seção 21: "Exemplos de uso
deverão permanecer atualizados e executáveis"). Todos os 7 comandos
já funcionam (ver a seção "Uso" do README raiz).

`snkb record` está totalmente conectado de ponta a ponta (Module
Specifications, Capítulos 3–10; ADRs 0004–0013): abre um navegador
Chromium real, aguarda o login manual, rastreia a navegação, coleta
elementos reais de DOM, gera seletores, captura screenshots e exporta
uma Base de Conhecimento completa para `<output_directory>/<session-id>/`.
Os testes automatizados só o exercitam contra fixtures HTML locais
(AI Coding Standards, seção 19 proíbe testes de tocar a internet real
ou uma instância real do ServiceNow) — a primeira execução contra uma
instância real é necessariamente um passo manual:

```bash
snkb record --instance-url https://sua-instancia.service-now.com
```

Uma janela visível (não headless) do Chromium é aberta; faça o login
manualmente (a ferramenta nunca automatiza o SSO da Microsoft nem
preenche formulário algum — RS-001). Navegue por algumas páginas
reais e então pressione Enter (ou Ctrl+C) no terminal para encerrar a
gravação. Inspecione `exports/<session-id>/session.json`,
`pages/*.json`, `selectors.json`, `screenshots/*.png` e
`manifest.json` para confirmar dados reais (não vazios).

Em seguida, `snkb status`/`validate`/`open`/`logs` descobrem essa
mesma sessão em disco (cada invocação da CLI é um processo novo, sem
acesso à memória do processo que gravou — ADR 0014) e `snkb config`
mostra a configuração efetiva carregada pelo Configuration Manager
(ADR 0015).
