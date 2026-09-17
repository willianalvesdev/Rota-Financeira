/* Rota Financeira: themes, accessible dialogs, form helpers and local charts. */
(() => {
    "use strict";

    const themeKey = "rota-financeira-theme";
    let savedTheme = "light";
    try {
        savedTheme = localStorage.getItem(themeKey) === "dark" ? "dark" : "light";
    } catch {
        // The application remains usable when browser storage is unavailable.
    }
    document.documentElement.dataset.theme = savedTheme;

    const init = () => {
        const updateThemeButtons = () => {
            const isDark = document.documentElement.dataset.theme === "dark";
            document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
                button.setAttribute("aria-label", isDark ? "Ativar tema claro" : "Ativar tema escuro");
                button.title = isDark ? "Ativar tema claro" : "Ativar tema escuro";
            });
        };
        updateThemeButtons();
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.addEventListener("click", () => {
                const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
                document.documentElement.dataset.theme = theme;
                try { localStorage.setItem(themeKey, theme); } catch { /* Storage is optional. */ }
                updateThemeButtons();
            });
        });

        document.querySelectorAll("[data-password-toggle]").forEach((button) => {
            const input = document.getElementById(button.dataset.passwordToggle);
            if (!input) return;
            const initialLabel = button.getAttribute("aria-label") || "Mostrar senha";
            button.addEventListener("click", () => {
                const show = input.type === "password";
                input.type = show ? "text" : "password";
                button.setAttribute("aria-pressed", String(show));
                button.setAttribute("aria-label", show ? initialLabel.replace("Mostrar", "Ocultar") : initialLabel);
            });
        });

        document.querySelectorAll("[data-confirm-password]").forEach((form) => {
            const password = form.elements.namedItem("senha");
            const confirmation = form.elements.namedItem("confirmar_senha");
            const validate = () => {
                confirmation.setCustomValidity(confirmation.value && confirmation.value !== password.value ? "As senhas precisam ser iguais." : "");
            };
            password.addEventListener("input", validate);
            confirmation.addEventListener("input", validate);
        });

        const dialogDefaults = new WeakMap();
        const dialogOpeners = new WeakMap();
        document.querySelectorAll("dialog").forEach((dialog) => {
            const form = dialog.querySelector("form");
            dialogDefaults.set(dialog, {
                action: form.getAttribute("action"),
                title: dialog.querySelector("[data-dialog-title]")?.textContent,
                description: dialog.querySelector("[data-dialog-description]")?.textContent,
                submit: dialog.querySelector("[data-dialog-submit]")?.textContent,
            });
            dialog.addEventListener("close", () => {
                if (!document.querySelector("dialog[open]")) document.body.classList.remove("dialog-open");
                dialogOpeners.get(dialog)?.focus();
            });
            dialog.addEventListener("click", (event) => {
                if (event.target !== dialog) return;
                const rect = dialog.getBoundingClientRect();
                if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
            });
        });

        document.addEventListener("click", (event) => {
            const dismiss = event.target.closest("[data-dismiss-flash]");
            if (dismiss) dismiss.closest(".flash")?.remove();
            const close = event.target.closest("[data-close-dialog]");
            if (close) close.closest("dialog")?.close();
            const trigger = event.target.closest("[data-dialog]");
            if (!trigger) return;
            const dialog = document.getElementById(trigger.dataset.dialog);
            if (!(dialog instanceof HTMLDialogElement)) return;
            const form = dialog.querySelector("form");
            const defaults = dialogDefaults.get(dialog);
            form.reset();
            const action = trigger.dataset.action || defaults.action;
            if (action) form.setAttribute("action", action);
            else form.removeAttribute("action");
            const title = dialog.querySelector("[data-dialog-title]");
            const description = dialog.querySelector("[data-dialog-description]");
            const submit = dialog.querySelector("[data-dialog-submit]");
            if (title) title.textContent = trigger.dataset.title || defaults.title;
            if (description) description.textContent = trigger.dataset.description || defaults.description;
            if (submit) submit.textContent = trigger.dataset.submitLabel || defaults.submit;
            form.querySelectorAll("[data-create-min]").forEach((input) => {
                if (trigger.dataset.edit === "true") input.removeAttribute("min");
                else input.min = input.dataset.createMin;
            });
            if (trigger.dataset.values) {
                try {
                    const values = JSON.parse(trigger.dataset.values);
                    Object.entries(values).forEach(([name, value]) => {
                        const input = form.elements.namedItem(name);
                        if (input instanceof HTMLInputElement || input instanceof HTMLSelectElement) input.value = value ?? "";
                    });
                } catch {
                    return;
                }
            }
            dialogOpeners.set(dialog, trigger);
            dialog.showModal();
            document.body.classList.add("dialog-open");
        });

        // Disable only the submitted button to avoid accidental repeated writes.
        document.addEventListener("submit", (event) => {
            const button = event.submitter;
            if (!button || event.defaultPrevented) return;
            button.disabled = true;
            button.dataset.submitting = "true";
            button.setAttribute("aria-busy", "true");
        });
        window.addEventListener("pageshow", () => {
            document.querySelectorAll("[data-submitting]").forEach((button) => {
                button.disabled = false;
                button.removeAttribute("data-submitting");
                button.removeAttribute("aria-busy");
            });
        });

        const updateNavigation = () => {
            const hash = window.location.hash || "#visao-geral";
            document.querySelectorAll(".sidebar-nav .nav-link").forEach((link) => {
                const active = link.hash === hash;
                link.classList.toggle("is-active", active);
                if (active) link.setAttribute("aria-current", "location");
                else link.removeAttribute("aria-current");
            });
        };
        window.addEventListener("hashchange", updateNavigation);
        updateNavigation();

        document.querySelectorAll("[data-chart]").forEach((container) => {
            renderChart(container);
            let width = container.getBoundingClientRect().width;
            if (typeof ResizeObserver === "undefined") return;
            const observer = new ResizeObserver(() => {
                const nextWidth = container.getBoundingClientRect().width;
                if (Math.abs(nextWidth - width) < 1) return;
                width = nextWidth;
                renderChart(container);
            });
            observer.observe(container);
        });
    };

    function renderChart(container) {
        let data;
        try { data = JSON.parse(container.dataset.chart); } catch { return; }
        const months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
        const safeValues = (values) => Array.from({ length: 12 }, (_, i) => {
            const number = Number(values?.[i]);
            return Number.isFinite(number) && number > 0 ? number : 0;
        });
        const income = safeValues(data.receitas);
        const expenses = safeValues(data.despesas);
        const maximum = Math.max(...income, ...expenses);
        const formatter = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
        const axisFormatter = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 2 });
        const namespace = "http://www.w3.org/2000/svg";
        const node = (tag, attributes, content) => {
            const element = document.createElementNS(namespace, tag);
            Object.entries(attributes || {}).forEach(([key, value]) => element.setAttribute(key, String(value)));
            if (content !== undefined) element.textContent = content;
            return element;
        };
        const chartWidth = Math.max(260, Math.round(container.getBoundingClientRect().width));
        const chartHeight = chartWidth < 450 ? 215 : 255;
        const svg = node("svg", { viewBox: "0 0 " + chartWidth + " " + chartHeight, class: "chart-svg", role: "img", "aria-label": "Receitas e despesas mensais de " + data.ano + ". Consulte os valores na tabela abaixo." });
        svg.append(node("title", {}, "Receitas e despesas de " + data.ano));
        svg.append(node("desc", {}, maximum === 0 ? "Nenhuma transação registrada neste ano." : "Barras preenchidas representam receitas; barras com contorno representam despesas. Os valores completos estão disponíveis na tabela anual."));
        const plot = { left: 48, right: chartWidth - 12, top: 20, bottom: chartHeight - 36 };
        const upper = maximum > 0 ? Math.max(1, niceMaximum(maximum)) : 100;
        const height = plot.bottom - plot.top;
        for (let i = 0; i <= 4; i++) {
            const value = upper * i / 4;
            const y = plot.bottom - height * i / 4;
            svg.append(node("line", { x1: plot.left, x2: plot.right, y1: y, y2: y, class: "chart-grid" }));
            svg.append(node("text", { x: plot.left - 10, y: y + 4, "text-anchor": "end", class: "chart-label" }, axisFormatter.format(value)));
        }
        svg.append(node("text", { x: plot.left - 10, y: 9, "text-anchor": "end", class: "chart-label" }, "R$"));
        const groupWidth = (plot.right - plot.left) / 12;
        const barWidth = Math.max(3, Math.min(13, (groupWidth - 7) / 2));
        months.forEach((month, i) => {
            const x = plot.left + groupWidth * (i + .5);
            svg.append(node("text", { x, y: plot.bottom + 24, "text-anchor": "middle", class: "chart-label chart-label-month" }, chartWidth < 340 ? month.slice(0, 1) : month));
            [[income[i], "income", "Receitas", -barWidth - 1], [expenses[i], "expense", "Despesas", 2]].forEach(([value, kind, label, offset]) => {
                if (value === 0) return;
                const barHeight = Math.max(value / upper * height, 1);
                const bar = node("rect", { x: x + offset, y: plot.bottom - barHeight, width: barWidth, height: barHeight, rx: 2, class: "chart-bar chart-bar-" + kind });
                bar.append(node("title", {}, month + ": " + label + " " + formatter.format(value)));
                svg.append(bar);
            });
        });
        if (maximum === 0) svg.append(node("text", { x: (plot.left + plot.right) / 2, y: (plot.top + plot.bottom) / 2, "text-anchor": "middle", class: "chart-empty-label" }, chartWidth < 450 ? "Nenhuma transação neste ano" : "Seu ano começa com a primeira transação"));
        container.replaceChildren(svg);
    }

    function niceMaximum(value) {
        const magnitude = 10 ** Math.floor(Math.log10(value));
        return Math.ceil(value / magnitude / .5) * magnitude * .5;
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
