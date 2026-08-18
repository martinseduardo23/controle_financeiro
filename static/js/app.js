document.addEventListener("DOMContentLoaded", () => {

    const camposMoeda = document.querySelectorAll(
        ".currency-field"
    );


    /*
     * Remove caracteres inválidos,
     * mas permite que o usuário digite
     * normalmente enquanto está no campo.
     */
    function limparValor(valor) {

        valor = String(valor || "");

        valor = valor
            .replace(/[^\d,]/g, "");

        /*
         * Permite apenas uma vírgula.
         */
        const partes = valor.split(",");

        if (partes.length > 2) {

            valor =
                partes[0] +
                "," +
                partes
                    .slice(1)
                    .join("");

        }

        /*
         * Limita os centavos a duas casas.
         */
        if (valor.includes(",")) {

            const partesValor =
                valor.split(",");

            valor =
                partesValor[0] +
                "," +
                partesValor[1]
                    .substring(0, 2);

        }

        return valor;
    }


    /*
     * Converte um valor brasileiro para número.
     *
     * Exemplos:
     *
     * 600       -> 600
     * 600,5     -> 600.5
     * 600,50    -> 600.5
     * 7000,50   -> 7000.5
     */
    function converterParaNumero(valor) {

        valor = limparValor(valor);

        if (!valor) {
            return 0;
        }

        valor = valor.replace(
            ",",
            "."
        );

        const numero =
            parseFloat(valor);

        return isNaN(numero)
            ? 0
            : numero;
    }


    /*
     * Formata somente quando o usuário
     * termina de editar o campo.
     */
    function formatarMoeda(valor) {

        const numero =
            converterParaNumero(valor);

        return numero.toLocaleString(
            "pt-BR",
            {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }
        );
    }


    camposMoeda.forEach((campo) => {

        /*
         * Quando a página abre, formata
         * o valor que já veio do servidor.
         */
        if (campo.value) {

            campo.value =
                formatarMoeda(
                    campo.value
                );

        }


        /*
         * Durante a digitação:
         *
         * NÃO transforma 6 em 6,00.
         *
         * Apenas limpa caracteres inválidos.
         */
        campo.addEventListener(
            "input",
            () => {

                const posicao =
                    campo.selectionStart;

                const valorAnterior =
                    campo.value;

                const valorLimpo =
                    limparValor(
                        valorAnterior
                    );

                campo.value =
                    valorLimpo;

                /*
                 * Mantém o cursor no lugar
                 * mais próximo possível.
                 */
                try {

                    campo.setSelectionRange(
                        posicao,
                        posicao
                    );

                } catch (erro) {
                    // Ignora
                }


                /*
                 * Permite que outras partes
                 * da página reajam ao valor.
                 */
                campo.dispatchEvent(
                    new CustomEvent(
                        "valorMoedaAlterado"
                    )
                );

            }
        );


        /*
         * Ao sair do campo,
         * aplica a formatação brasileira.
         */
        campo.addEventListener(
            "blur",
            () => {

                campo.value =
                    formatarMoeda(
                        campo.value
                    );

                campo.dispatchEvent(
                    new CustomEvent(
                        "valorMoedaAlterado"
                    )
                );

            }
        );


        /*
         * Ao entrar no campo,
         * seleciona o conteúdo.
         */
        campo.addEventListener(
            "focus",
            () => {

                campo.select();

            }
        );

    });

});document.addEventListener("DOMContentLoaded", () => {

    const camposMoeda = document.querySelectorAll(
        ".currency-field"
    );


    /*
     * Remove caracteres inválidos,
     * mas permite que o usuário digite
     * normalmente enquanto está no campo.
     */
    function limparValor(valor) {

        valor = String(valor || "");

        valor = valor
            .replace(/[^\d,]/g, "");

        /*
         * Permite apenas uma vírgula.
         */
        const partes = valor.split(",");

        if (partes.length > 2) {

            valor =
                partes[0] +
                "," +
                partes
                    .slice(1)
                    .join("");

        }

        /*
         * Limita os centavos a duas casas.
         */
        if (valor.includes(",")) {

            const partesValor =
                valor.split(",");

            valor =
                partesValor[0] +
                "," +
                partesValor[1]
                    .substring(0, 2);

        }

        return valor;
    }


    /*
     * Converte um valor brasileiro para número.
     *
     * Exemplos:
     *
     * 600       -> 600
     * 600,5     -> 600.5
     * 600,50    -> 600.5
     * 7000,50   -> 7000.5
     */
    function converterParaNumero(valor) {

        valor = limparValor(valor);

        if (!valor) {
            return 0;
        }

        valor = valor.replace(
            ",",
            "."
        );

        const numero =
            parseFloat(valor);

        return isNaN(numero)
            ? 0
            : numero;
    }


    /*
     * Formata somente quando o usuário
     * termina de editar o campo.
     */
    function formatarMoeda(valor) {

        const numero =
            converterParaNumero(valor);

        return numero.toLocaleString(
            "pt-BR",
            {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }
        );
    }


    camposMoeda.forEach((campo) => {

        /*
         * Quando a página abre, formata
         * o valor que já veio do servidor.
         */
        if (campo.value) {

            campo.value =
                formatarMoeda(
                    campo.value
                );

        }


        /*
         * Durante a digitação:
         *
         * NÃO transforma 6 em 6,00.
         *
         * Apenas limpa caracteres inválidos.
         */
        campo.addEventListener(
            "input",
            () => {

                const posicao =
                    campo.selectionStart;

                const valorAnterior =
                    campo.value;

                const valorLimpo =
                    limparValor(
                        valorAnterior
                    );

                campo.value =
                    valorLimpo;

                /*
                 * Mantém o cursor no lugar
                 * mais próximo possível.
                 */
                try {

                    campo.setSelectionRange(
                        posicao,
                        posicao
                    );

                } catch (erro) {
                    // Ignora
                }


                /*
                 * Permite que outras partes
                 * da página reajam ao valor.
                 */
                campo.dispatchEvent(
                    new CustomEvent(
                        "valorMoedaAlterado"
                    )
                );

            }
        );


        /*
         * Ao sair do campo,
         * aplica a formatação brasileira.
         */
        campo.addEventListener(
            "blur",
            () => {

                campo.value =
                    formatarMoeda(
                        campo.value
                    );

                campo.dispatchEvent(
                    new CustomEvent(
                        "valorMoedaAlterado"
                    )
                );

            }
        );


        /*
         * Ao entrar no campo,
         * seleciona o conteúdo.
         */
        campo.addEventListener(
            "focus",
            () => {

                campo.select();

            }
        );

    });

});