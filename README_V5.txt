FINANCEIRO - VERSAO 5

Alteração principal:
- Campos monetários agora usam máscara de moeda brasileira.
- O prefixo R$ fica visível no campo.
- O valor começa em 0,00.
- A digitação é formatada automaticamente como moeda brasileira.
- Exemplos:
  1 -> R$ 0,01
  123 -> R$ 1,23
  12345 -> R$ 123,45
  123456 -> R$ 1.234,56
- Aplicado em:
  - Novo lançamento > Valor
  - Nova conta > Saldo inicial
- O backend converte corretamente o formato brasileiro para o banco SQLite.

Para instalar:
1. Extraia o ZIP.
2. Mantenha seu financeiro.db se já existir.
3. Execute o projeto normalmente.
