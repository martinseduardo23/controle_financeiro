document.addEventListener("DOMContentLoaded", () => {

    const camposMoeda = document.querySelectorAll(
        ".currency-field, .money-input"
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

    // =====================================================
    // FECHAR ALERTAS (FLASH MESSAGES)
    // =====================================================
    document.querySelectorAll(".alert-close").forEach((btn) => {
        btn.addEventListener("click", () => {
            const alert = btn.closest(".alert");
            if (alert) {
                alert.style.opacity = "0";
                alert.style.transform = "translateY(-8px)";
                setTimeout(() => alert.remove(), 250);
            }
        });
    });

    // Auto-dismiss em alertas de sucesso após 5 segundos
    document.querySelectorAll(".alert-success").forEach((alert) => {
        setTimeout(() => {
            if (alert && alert.parentElement) {
                alert.style.opacity = "0";
                alert.style.transform = "translateY(-8px)";
                setTimeout(() => alert.remove(), 250);
            }
        }, 5000);
    });

    // =====================================================
    // MENU MOBILE / SIDEBAR TOGGLE
    // =====================================================
    const toggleBtn = document.getElementById("sidebar-toggle");
    const sidebar = document.querySelector(".sidebar");
    const overlay = document.getElementById("sidebar-overlay");

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener("click", () => {
            sidebar.classList.toggle("open");
            if (overlay) overlay.classList.toggle("active");
        });
    }

    if (overlay) {
        overlay.addEventListener("click", () => {
            if (sidebar) sidebar.classList.remove("open");
            overlay.classList.remove("active");
        });
    }

    // =====================================================
    // CONTROLE DE MODO DE LAYOUT (RESPONSIVO vs DESKTOP)
    // =====================================================
    function obterModoLayout() {
        const salvo = localStorage.getItem("modo_layout");
        if (salvo === "responsive" || salvo === "desktop") {
            return salvo;
        }
        return window.innerWidth <= 768 ? "responsive" : "desktop";
    }

    function aplicarModoLayout(modo, animar = false) {
        if (!modo) modo = obterModoLayout();

        document.documentElement.setAttribute("data-layout-mode", modo);
        document.body.classList.remove("mode-responsive", "mode-desktop");
        document.body.classList.add(modo === "responsive" ? "mode-responsive" : "mode-desktop");

        const btnResp = document.getElementById("btn-layout-responsive");
        const btnDesk = document.getElementById("btn-layout-desktop");
        if (btnResp && btnDesk) {
            btnResp.classList.toggle("active", modo === "responsive");
            btnDesk.classList.toggle("active", modo === "desktop");
        }

        const sidebarText = document.getElementById("sidebar-layout-text");
        const sidebarIcon = document.getElementById("sidebar-layout-icon");
        if (sidebarText) {
            sidebarText.textContent = modo === "responsive" ? "Visualização: Responsiva" : "Visualização: Desktop";
        }
        if (sidebarIcon) {
            if (modo === "responsive") {
                sidebarIcon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"/>';
            } else {
                sidebarIcon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>';
            }
        }

        const meta = document.getElementById("meta-viewport");
        if (meta) {
            if (modo === "desktop" && window.innerWidth <= 768) {
                meta.setAttribute("content", "width=1200, initial-scale=0.35, user-scalable=yes");
            } else {
                meta.setAttribute("content", "width=device-width, initial-scale=1.0, maximum-scale=5.0");
            }
        }

        localStorage.setItem("modo_layout", modo);

        if (animar) {
            mostrarToastModo(
                modo === "responsive"
                    ? "📱 Modo Responsivo ativado (Celular / Compacto)"
                    : "💻 Modo Desktop ativado (Visão Completa / Computador)"
            );
        }
    }

    function alternarModoLayout(forcarModo) {
        const atual = document.documentElement.getAttribute("data-layout-mode") || obterModoLayout();
        const novo = forcarModo || (atual === "responsive" ? "desktop" : "responsive");
        aplicarModoLayout(novo, true);
    }

    function mostrarToastModo(msg) {
        let toast = document.getElementById("toast-layout-mode");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "toast-layout-mode";
            toast.className = "toast-layout-mode";
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        toast.classList.add("visible");
        clearTimeout(toast._timeout);
        toast._timeout = setTimeout(() => {
            toast.classList.remove("visible");
        }, 2200);
    }

    // Expondo globalmente para chamadas de onclick
    window.alternarModoLayout = alternarModoLayout;
    window.aplicarModoLayout = aplicarModoLayout;

    // Inicializa o modo atual
    aplicarModoLayout(obterModoLayout(), false);

    // Fecha sidebar ao clicar em um link em modo responsivo ou telas mobile
    document.querySelectorAll(".sidebar a").forEach((link) => {
        link.addEventListener("click", () => {
            const modoAtual = document.documentElement.getAttribute("data-layout-mode");
            if (window.innerWidth <= 768 || modoAtual === "responsive") {
                if (sidebar) sidebar.classList.remove("open");
                if (overlay) overlay.classList.remove("active");
            }
        });
    });

    // Confirmação para botões com [data-confirm]
    document.querySelectorAll("[data-confirm]").forEach((el) => {
        el.addEventListener("submit", (e) => {
            const msg = el.getAttribute("data-confirm") || "Tem certeza que deseja executar esta ação?";
            if (!confirm(msg)) {
                e.preventDefault();
            }
        });
    });

});