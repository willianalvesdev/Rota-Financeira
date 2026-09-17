/* Rota Financeira: consent-aware preferences, accessible dialogs and local charts. */
(() => {
    "use strict";

    const storageKeys = {
        consent: "rota-cookie-consent",
        theme: "rota-financeira-theme",
        sidebar: "rota-sidebar-collapsed",
        chart: "rota-chart-type",
    };
    const readConsent = () => {
        try {
            const value = JSON.parse(localStorage.getItem(storageKeys.consent));
            if (!value || typeof value.preferences !== "boolean" || typeof value.updatedAt !== "string") return null;
            const updated = new Date(value.updatedAt);
            if (!Number.isFinite(updated.getTime()) || updated.getTime() > Date.now()) return null;
            const expires = new Date(updated);
            expires.setUTCMonth(expires.getUTCMonth() + 6);
            return expires.getTime() > Date.now() ? value : null;
        } catch { return null; }
    };
    let consent = readConsent();
    const readPreference = (key, fallback) => {
        if (!consent?.preferences) return fallback;
        try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
    };
    const savePreference = (key, value) => {
        if (!readConsent()?.preferences) return;
        try { localStorage.setItem(key, value); } catch { /* Preferences are optional. */ }
    };
    const theme = readPreference(storageKeys.theme, "dark");
    document.documentElement.dataset.theme = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.sidebarCollapsed = readPreference(storageKeys.sidebar, "false") === "true" ? "true" : "false";
    let chartType = readPreference(storageKeys.chart, "line") === "bar" ? "bar" : "line";

    const init = () => {
        const updateThemeButtons = () => {
            const isDark = document.documentElement.dataset.theme === "dark";
            document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
                const label = isDark ? "Ativar tema claro" : "Ativar tema escuro";
                button.setAttribute("aria-label", label);
                button.title = label;
            });
        };
        updateThemeButtons();
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.addEventListener("click", () => {
                const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
                document.documentElement.dataset.theme = nextTheme;
                savePreference(storageKeys.theme, nextTheme);
                updateThemeButtons();
            });
        });

        const updateSidebarButtons = () => {
            const collapsed = document.documentElement.dataset.sidebarCollapsed === "true";
            document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
                button.setAttribute("aria-expanded", String(!collapsed));
                button.setAttribute("aria-label", collapsed ? "Expandir menu" : "Recolher menu");
                button.title = collapsed ? "Expandir menu" : "Recolher menu";
            });
        };
        updateSidebarButtons();
        document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
            button.addEventListener("click", () => {
                const collapsed = document.documentElement.dataset.sidebarCollapsed !== "true";
                document.documentElement.dataset.sidebarCollapsed = String(collapsed);
                savePreference(storageKeys.sidebar, String(collapsed));
                updateSidebarButtons();
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
            if (!password || !confirmation) return;
            const validate = () => confirmation.setCustomValidity(
                confirmation.value && confirmation.value !== password.value ? "As senhas precisam ser iguais." : ""
            );
            password.addEventListener("input", validate);
            confirmation.addEventListener("input", validate);
        });

        const dialogDefaults = new WeakMap();
        const dialogOpeners = new WeakMap();
        const cookieDialog = document.getElementById("cookie-dialog");
        const updateCookieStatus = () => {
            document.querySelectorAll("[data-cookie-status]").forEach((element) => {
                element.textContent = consent ? (consent.preferences ? "Permitidas" : "Desativadas") : "Opcionais";
            });
        };
        const chooseCookies = (preferences) => {
            consent = { preferences, updatedAt: new Date().toISOString() };
            try {
                localStorage.setItem(storageKeys.consent, JSON.stringify(consent));
                if (preferences) {
                    localStorage.setItem(storageKeys.theme, document.documentElement.dataset.theme);
                    localStorage.setItem(storageKeys.sidebar, document.documentElement.dataset.sidebarCollapsed);
                    localStorage.setItem(storageKeys.chart, chartType);
                } else {
                    [storageKeys.theme, storageKeys.sidebar, storageKeys.chart].forEach((key) => localStorage.removeItem(key));
                }
            } catch { /* Essential functionality never depends on browser storage. */ }
            updateCookieStatus();
        };
        updateCookieStatus();
        document.querySelectorAll("dialog").forEach((dialog) => {
            const form = dialog.querySelector("form");
            dialogDefaults.set(dialog, {
                action: form?.getAttribute("action"),
                title: dialog.querySelector("[data-dialog-title]")?.textContent,
                description: dialog.querySelector("[data-dialog-description]")?.textContent,
                submit: dialog.querySelector("[data-dialog-submit]")?.textContent,
            });
            dialog.addEventListener("close", () => {
                if (dialog === cookieDialog && !consent) chooseCookies(false);
                if (!document.querySelector("dialog[open]")) document.body.classList.remove("dialog-open");
                dialogOpeners.get(dialog)?.focus();
            });
            dialog.addEventListener("click", (event) => {
                if (event.target !== dialog) return;
                const rect = dialog.getBoundingClientRect();
                if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
            });
        });
        const openDialog = (dialog, trigger) => {
            if (!(dialog instanceof HTMLDialogElement) || dialog.open) return;
            const form = dialog.querySelector("form");
            const defaults = dialogDefaults.get(dialog) || {};
            const data = trigger?.dataset || {};
            if (form) {
                form.reset();
                const action = data.action || defaults.action;
                if (action) form.setAttribute("action", action);
                else form.removeAttribute("action");
                form.querySelectorAll("[data-create-min]").forEach((input) => {
                    if (data.edit === "true") input.removeAttribute("min");
                    else input.min = input.dataset.createMin;
                });
                if (data.values) {
                    try {
                        Object.entries(JSON.parse(data.values)).forEach(([name, value]) => {
                            const input = form.elements.namedItem(name);
                            if (input instanceof HTMLInputElement || input instanceof HTMLSelectElement) input.value = value ?? "";
                        });
                    } catch { return; }
                }
            }
            const title = dialog.querySelector("[data-dialog-title]");
            const description = dialog.querySelector("[data-dialog-description]");
            const submit = dialog.querySelector("[data-dialog-submit]");
            if (title) title.textContent = data.title || defaults.title;
            if (description) description.textContent = data.description || defaults.description;
            if (submit) submit.textContent = data.submitLabel || defaults.submit;
            if (trigger) dialogOpeners.set(dialog, trigger);
            if (dialog === cookieDialog) updateCookieStatus();
            dialog.showModal();
            document.body.classList.add("dialog-open");
        };
        document.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof Element)) return;
            const dismiss = target.closest("[data-dismiss-flash]");
            if (dismiss) dismiss.closest(".flash")?.remove();
            const choice = target.closest("[data-cookie-choice]");
            if (choice) {
                chooseCookies(choice.dataset.cookieChoice === "true");
                cookieDialog?.close();
            }
            const close = target.closest("[data-close-dialog]");
            if (close) close.closest("dialog")?.close();
            const trigger = target.closest("[data-dialog]");
            if (trigger) openDialog(document.getElementById(trigger.dataset.dialog), trigger);
        });
        if (!consent && cookieDialog) openDialog(cookieDialog);
        window.addEventListener("storage", (event) => {
            if (event.key === storageKeys.consent) {
                consent = readConsent();
                updateCookieStatus();
            }
        });

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

        const charts = document.querySelectorAll("[data-chart]");
        const updateChartButtons = () => {
            document.querySelectorAll("[data-chart-type]").forEach((button) => {
                button.setAttribute("aria-pressed", String(button.dataset.chartType === chartType));
            });
        };
        updateChartButtons();
        document.querySelectorAll("[data-chart-type]").forEach((button) => {
            button.addEventListener("click", () => {
                chartType = button.dataset.chartType === "bar" ? "bar" : "line";
                savePreference(storageKeys.chart, chartType);
                updateChartButtons();
                charts.forEach(renderChart);
            });
        });
        charts.forEach((container, index) => {
            container.dataset.chartId = String(index);
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
        const axisFormatter = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
        const namespace = "http://www.w3.org/2000/svg";
        const node = (tag, attributes, content) => {
            const element = document.createElementNS(namespace, tag);
            Object.entries(attributes || {}).forEach(([key, value]) => element.setAttribute(key, String(value)));
            if (content !== undefined) element.textContent = content;
            return element;
        };
        const chartWidth = Math.max(260, Math.round(container.getBoundingClientRect().width));
        const chartHeight = chartWidth < 450 ? 245 : 285;
        const svg = node("svg", { viewBox: "0 0 " + chartWidth + " " + chartHeight, class: "chart-svg", role: "group", "aria-label": "Receitas e despesas mensais de " + data.ano + ". Use as setas do teclado para consultar os meses." });
        svg.append(node("title", {}, "Receitas e despesas de " + data.ano));
        svg.append(node("desc", {}, maximum === 0 ? "Nenhuma transação registrada neste ano." : "Receitas em verde e despesas em vermelho. Cada mês pode ser consultado com o ponteiro ou teclado. Os valores também estão disponíveis na tabela anual."));
        const plot = { left: 54, right: chartWidth - 12, top: 24, bottom: chartHeight - 38 };
        const upper = maximum > 0 ? Math.max(1, niceMaximum(maximum)) : 100;
        const height = plot.bottom - plot.top;
        const groupWidth = (plot.right - plot.left) / 12;
        const xAt = (index) => plot.left + groupWidth * (index + .5);
        const yAt = (value) => plot.bottom - value / upper * height;
        for (let i = 0; i <= 4; i++) {
            const value = upper * i / 4;
            const y = plot.bottom - height * i / 4;
            svg.append(node("line", { x1: plot.left, x2: plot.right, y1: y, y2: y, class: "chart-grid" }));
            svg.append(node("text", { x: plot.left - 9, y: y + 4, "text-anchor": "end", class: "chart-label" }, axisFormatter.format(value)));
        }
        svg.append(node("text", { x: plot.left - 9, y: 12, "text-anchor": "end", class: "chart-label" }, "R$"));
        months.forEach((month, i) => {
            svg.append(node("text", { x: xAt(i), y: plot.bottom + 27, "text-anchor": "middle", class: "chart-label chart-label-month" }, chartWidth < 360 ? month.slice(0, 1) : month));
        });
        if (maximum > 0 && chartType === "line") {
            const defs = node("defs");
            [["income", income], ["expense", expenses]].forEach(([kind, values]) => {
                const id = "chart-gradient-" + kind + "-" + container.dataset.chartId;
                const gradient = node("linearGradient", { id, x1: "0", y1: "0", x2: "0", y2: "1" });
                gradient.append(node("stop", { offset: "0%", "stop-opacity": ".25", class: "chart-gradient-" + kind }));
                gradient.append(node("stop", { offset: "100%", "stop-opacity": "0", class: "chart-gradient-" + kind }));
                defs.append(gradient);
                const points = values.map((value, i) => xAt(i) + " " + yAt(value));
                const linePath = "M" + points.join(" L");
                const areaPath = linePath + " L" + xAt(11) + " " + plot.bottom + " L" + xAt(0) + " " + plot.bottom + " Z";
                svg.append(node("path", { d: areaPath, fill: "url(#" + id + ")", class: "chart-area" }));
                svg.append(node("path", { d: linePath, class: "chart-line chart-line-" + kind }));
            });
            svg.prepend(defs);
        } else if (maximum > 0) {
            const barWidth = Math.max(3, Math.min(15, (groupWidth - 7) / 2));
            months.forEach((month, i) => {
                [[income[i], "income", -barWidth - 1], [expenses[i], "expense", 2]].forEach(([value, kind, offset]) => {
                    if (value === 0) return;
                    const barHeight = Math.max(value / upper * height, 1);
                    const bar = node("rect", { x: xAt(i) + offset, y: plot.bottom - barHeight, width: barWidth, height: barHeight, rx: 2, class: "chart-bar chart-bar-" + kind });
                    svg.append(bar);
                });
            });
        }
        if (maximum === 0) {
            svg.append(node("text", { x: (plot.left + plot.right) / 2, y: (plot.top + plot.bottom) / 2, "text-anchor": "middle", class: "chart-empty-label" }, chartWidth < 450 ? "Nenhuma transação neste ano" : "Seu ano começa com a primeira transação"));
        }

        const tooltip = document.createElement("div");
        tooltip.className = "chart-tooltip";
        tooltip.hidden = true;
        tooltip.setAttribute("role", "status");
        tooltip.setAttribute("aria-live", "polite");
        const hint = document.createElement("p");
        hint.className = "chart-hint";
        hint.textContent = "Selecione um mês para consultar os detalhes. No teclado, use as setas.";
        const targets = [];
        let pinnedIndex = null;
        const cents = (value) => Math.round((value + Number.EPSILON) * 100) / 100;
        const appendMoney = (element, value, signed = false) => {
            if (signed && value > 0) element.append(document.createTextNode("+ "));
            formatter.formatToParts(value).forEach((part) => {
                const span = document.createElement("span");
                span.className = ["decimal", "fraction"].includes(part.type) ? "money-cents" : part.type === "currency" ? "money-symbol" : "money-whole";
                span.textContent = part.value;
                element.append(span);
            });
        };
        const activate = (index) => {
            container.dataset.activeMonth = String(index);
            targets.forEach((target, i) => {
                target.classList.toggle("is-active", i === index);
                target.setAttribute("tabindex", i === index ? "0" : "-1");
            });
            const result = cents(income[index] - expenses[index]);
            const month = document.createElement("span");
            month.className = "chart-tooltip-month";
            month.textContent = months[index] + " " + data.ano + " · Resultado do mês";
            const amount = document.createElement("strong");
            amount.className = "chart-tooltip-value financial-amount " + (result > 0 ? "positive-text" : result < 0 ? "negative-text" : "");
            appendMoney(amount, result, true);
            const detail = document.createElement("div");
            detail.className = "chart-tooltip-detail";
            [["Receitas", income[index], "positive-text"], ["Despesas", expenses[index], "negative-text"]].forEach(([label, value, color]) => {
                const item = document.createElement("span");
                item.className = "financial-amount " + color;
                item.append(document.createTextNode(label + " "));
                appendMoney(item, value);
                detail.append(item);
            });
            const change = document.createElement("div");
            change.className = "chart-tooltip-change";
            if (index === 0) {
                change.textContent = "Mês anterior indisponível neste gráfico.";
            } else {
                const previous = cents(income[index - 1] - expenses[index - 1]);
                const difference = cents(result - previous);
                if (difference === 0) {
                    change.textContent = "Sem variação em relação a " + months[index - 1] + ".";
                } else {
                    change.append(document.createTextNode("Em relação a " + months[index - 1] + ": "));
                    const variation = document.createElement("strong");
                    variation.className = "financial-amount " + (difference > 0 ? "positive-text" : "negative-text");
                    appendMoney(variation, difference, true);
                    change.append(variation);
                    if (previous === 0) {
                        change.append(document.createTextNode(" · sem base percentual"));
                    } else {
                        const percentage = difference / Math.abs(previous) * 100;
                        const formatted = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(Math.abs(percentage));
                        change.append(document.createTextNode(" (" + (percentage > 0 ? "+" : "−") + formatted + "%)"));
                    }
                }
            }
            tooltip.replaceChildren(month, amount, detail, change);
            tooltip.hidden = false;
        };
        const hideTooltip = () => {
            tooltip.hidden = true;
            targets.forEach((target) => target.classList.remove("is-active"));
        };
        months.forEach((month, i) => {
            const label = month + "/" + data.ano + ". Receitas " + formatter.format(income[i]) + ". Despesas " + formatter.format(expenses[i]) + ". Resultado " + formatter.format(income[i] - expenses[i]) + ".";
            const target = node("g", { class: "chart-point", role: "button", tabindex: i === 0 ? "0" : "-1", "aria-label": label });
            target.append(node("line", { x1: xAt(i), x2: xAt(i), y1: plot.top, y2: plot.bottom, class: "chart-focus-line" }));
            target.append(node("rect", { x: plot.left + groupWidth * i, y: plot.top, width: groupWidth, height, fill: "transparent" }));
            if (maximum > 0 && chartType === "line") {
                target.append(node("circle", { cx: xAt(i), cy: yAt(income[i]), r: 4, class: "chart-focus-dot chart-focus-income" }));
                target.append(node("circle", { cx: xAt(i), cy: yAt(expenses[i]), r: 4, class: "chart-focus-dot chart-focus-expense" }));
            }
            target.addEventListener("pointerenter", () => activate(i));
            target.addEventListener("focus", () => activate(i));
            target.addEventListener("click", () => {
                pinnedIndex = pinnedIndex === i ? null : i;
                if (pinnedIndex === null) hideTooltip();
                else activate(i);
            });
            target.addEventListener("keydown", (event) => {
                if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
                    event.preventDefault();
                    targets[(i + (event.key === "ArrowRight" ? 1 : 11)) % 12].focus();
                } else if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    activate(i);
                }
            });
            targets.push(target);
            svg.append(target);
        });
        container.replaceChildren(svg, tooltip, hint);
        container.onpointerleave = () => {
            if (pinnedIndex === null && !container.contains(document.activeElement)) hideTooltip();
        };
        container.onfocusout = () => {
            setTimeout(() => {
                if (pinnedIndex === null && !container.contains(document.activeElement)) hideTooltip();
            }, 0);
        };
    }

    function niceMaximum(value) {
        const magnitude = 10 ** Math.floor(Math.log10(value));
        return Math.ceil(value / magnitude / .5) * magnitude * .5;
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
