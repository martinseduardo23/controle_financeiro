document.addEventListener("DOMContentLoaded", () => {
    const camposMoeda = document.querySelectorAll(".currency-field");

    function formatarMoeda(valor) {
        let numeros = valor.replace(/\D/g, "");

        if (!numeros) {
            numeros = "0";
        }

        numeros = numeros.replace(/^0+(?=\d)/, "");

        const numero = parseInt(numeros, 10) / 100;

        return numero.toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function aplicarMascara(campo) {
        campo.value = formatarMoeda(campo.value);
    }

    camposMoeda.forEach((campo) => {
        aplicarMascara(campo);

        campo.addEventListener("input", () => {
            const posicaoFinal = campo.value.length;
            campo.value = formatarMoeda(campo.value);
            campo.setSelectionRange(
                campo.value.length,
                campo.value.length
            );
        });

        campo.addEventListener("focus", () => {
            campo.select();
        });
    });
});
