# Histórico do Projeto e Próximos Passos - Controle Financeiro

Documento de transição e contexto para continuidade do desenvolvimento do projeto no Antigravity / IDE em outro computador.

---

## 📌 Resumo do que foi feito até aqui

### 1. Backend e Regras de Negócio
- **Faturas de Cartão (`services/faturas_cartao.py` e `routes/compras_cartao.py`)**:
  - Implementada função `recalcular_valor_fatura(fatura)` que soma com precisão `Decimal` as parcelas reais atreladas, corrigindo o bug onde a fatura inflava ou duplicava valores na edição e não reduzia na exclusão de compras.
  - Implementada trava de segurança com `compra_tem_parcela_paga(compra)` para evitar exclusão/edição de compras com faturas já quitadas.
- **Proteção contra Erros 500 (Integridade Referencial)**:
  - Rotas de exclusão de `categorias.py`, `contas.py`, `cartoes.py` e `lancamentos.py` agora verificam dependências de chave estrangeira antes de deletar e exibem mensagens flash amigáveis na interface.
  - Criada rota de edição de contas (`/contas/editar/<id>`) e alternância de status ativo/inativo.
- **Performance e Dashboard (`routes/dashboard.py`)**:
  - As consultas agora filtram por mês no próprio banco de dados (removido o `Lancamento.query.all()`).
  - Identificação e alerta de despesas atrasadas no topo do Dashboard.
- **Relatórios Mensais (`routes/relatorios.py`)**:
  - Incluídos os gastos no cartão de crédito por categoria na competência do mês selecionado (`cartao_categorias`).
- **Otimização de Metas (`models/meta.py`)**:
  - Adicionado cache de feriados móveis (`_cache_feriados`) no cálculo de dias úteis com feriados nacionais.

### 2. Interface Visual (UI/UX)
- **Tema**: Dark Mode Absoluto (Preto verdadeiro `#000000` / `#0a0a0d`), estilo fintech moderna com tipografia Inter, cards com bordas suaves e badges de alto contraste.
- **Identidade**: Nome atualizado para **Controle Financeiro** (removido "Financeiro Pro"), novo ícone financeiro em SVG no logo.
- **Templates**: Todos os 20 templates foram modernizados e padronizados.
- **Facilidade**: Criado `iniciar.bat` para rodar o projeto com 2 cliques na porta 5000.

---

## 🎯 Próximas Funcionalidades Sugeridas para Implementar em Casa

1. **Transferência entre Contas Bancárias**:
   - Tela/modal de transferência entre duas contas cadastradas com débito na origem e crédito no destino.
2. **Lançamentos Recorrentes (Fixos/Assinaturas)**:
   - Salário, aluguel, condomínio, internet, streamings com repetição mensal automática.
3. **Teto de Gastos / Orçamento por Categoria (Budgeting)**:
   - Limite estipulado de gastos por categoria no mês com barra de acompanhamento no Dashboard.
4. **Importação de Extrato Bancário (OFX / CSV)**:
   - Upload de extratos bancários para conciliação e criação de lançamentos em lote.
5. **Gráficos Interativos (Chart.js)**:
   - Gráfico de evolução do patrimônio (linha/área) e rosca (donut) de despesas no Dashboard e Relatórios.
6. **Backup em 1 Clique**:
   - Botão para exportar e restaurar o arquivo `data/financeiro.db`.

---

## 💻 Como continuar no Antigravity em casa

1. Clonar o repositório ou dar `git pull`:
   ```bash
   git pull origin main
   ```
2. Iniciar o ambiente:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Colocar o seu banco com os dados reais (`data/financeiro.db`).
4. No chat do Antigravity em casa, basta pedir:
   > *"Leia o arquivo HISTORICO_PROJETO.md para entender todo o contexto do projeto e vamos implementar a funcionalidade X (ex.: Transferência entre contas)."*
