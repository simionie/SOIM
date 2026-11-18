"use strict";

$(() => {
    let currentProject = null;
    let activeSection = "Timeline";
    let editing = false;
    let opening = false;
    let running = false;
    let pollTimer;
    let pollGeneration = 0;
    let rowSequence = 0;
    const fieldsBySection = JSON.parse($("#form-fields").text());
    const productNames = JSON.parse($("#product-names").text());
    const productModes = JSON.parse($("#product-modes").text());
    let runPreferences = JSON.parse($("#run-preferences").text());
    let browseGeneration = 0;
    let browseDirectory = "";
    let dropGeneration = 0;
    const rowLabels = { Timeline: "Interval", Products: "Product", Instruments: "Instrument" };
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    const api = (url, method, data) => $.ajax({
        url,
        method,
        dataType: "json",
        contentType: "application/json",
        data: method === "GET" ? data : JSON.stringify(data),
    });

    function message(selector, text = "") {
        $(selector).text(text).prop("hidden", !text);
    }

    function showError(selector, error) {
        message(selector, error.responseJSON?.error || "Could not complete the request.");
    }

    function section() {
        return currentProject.sections.find(item => item.label === activeSection);
    }

    function updateControls() {
        $("#projects button").prop("disabled", editing || opening);
        $("[data-bs-target='#new-project']").prop("disabled", editing || opening);
        $("#sections button").prop("disabled", editing || opening);
        $("#show-run").prop("disabled", editing || opening || running ||
            currentProject?.sections.some(item => item.error));
        $("#edit-section").prop("disabled", opening || running);
    }

    function renderSection(preserveExpanded = false) {
        const item = section();
        $("#sections button").each(function () {
            const selected = this.dataset.section === activeSection;
            $(this).toggleClass("active", selected).attr("aria-pressed", selected);
        });
        $("#section-name").text(item.filename || item.label);
        message("#section-error", item.error);
        $("#edit-section").prop("hidden", editing || Boolean(item.error));
        $("#editor").prop("hidden", Boolean(item.error));
        $("#edit-actions").prop("hidden", !editing);
        $("#add-row").prop("hidden", activeSection === "Scenario")
            .text("Add " + rowLabels[activeSection]);
        const expanded = preserveExpanded
            ? $("#section-fields > details").map(function () { return this.open; }).get()
            : [];
        $("#section-fields").empty();
        (item.rows || []).forEach((row, index) => appendRow(row, Boolean(expanded[index])));
        updateRows();
        updateControls();
    }

    function appendRow(values = {}, open = false) {
        const sequence = ++rowSequence;
        const group = $("<fieldset>", { class: "config-group" });
        let entry = group;
        if (activeSection !== "Scenario") {
            const labelId = `config-${sequence}-summary`;
            entry = $("<details>", { class: "config-entry" }).prop("open", open);
            const summary = $("<summary>", { id: labelId, class: "config-summary" }).appendTo(entry);
            $("<span>", { class: "config-title" }).appendTo(summary);
            $("<span>", { class: "config-caption text-secondary small" }).appendTo(summary);
            group.attr("aria-labelledby", labelId).appendTo(entry);
        }
        const grid = $("<div>", { class: "row g-3" }).appendTo(group);
        for (const [key, label, description, required] of fieldsBySection[activeSection]) {
            if (key === "output") {
                $("<input>", { type: "hidden", "data-key": key }).val(values[key] ?? "").appendTo(grid);
                continue;
            }
            const id = `config-${sequence}-${grid.children().length}`;
            const field = $("<div>", { class: key === "mode" ? "col-12" : "col-12 col-md-6" }).appendTo(grid);
            if (key === "mode") {
                $("<span>", { id: id + "-label", class: "form-label d-block" }).text(label).appendTo(field);
            } else {
                $("<label>", { for: id, class: "form-label" }).text(label).appendTo(field);
            }
            const attributes = {
                id,
                "data-key": key,
                "aria-describedby": key === "stop" ? id + "-help " + id + "-error" : id + "-help",
            };
            if (key === "instruments" && editing) {
                appendChannelMenu(field, attributes, values[key]);
            } else if (key === "instrument") {
                appendChannelSelect(field, attributes, values[key]);
            } else if (key === "product") {
                appendProductSelect(field, attributes, values[key] ?? "");
            } else if (key === "mode") {
                $("<input>", { ...attributes, type: "hidden" }).val(values[key] ?? "").appendTo(field);
                $("<div>", {
                    class: "mode-options",
                    role: "group",
                    "aria-labelledby": id + "-label",
                    "aria-describedby": id + "-help",
                }).appendTo(field);
            } else if (editing && (key === "start" || key === "stop")) {
                appendUtcPicker(field, attributes, values[key] ?? "");
            } else {
                $("<input>", { ...attributes, type: "text", class: "form-control", spellcheck: "false" })
                    .val(values[key] ?? "").prop({ readOnly: !editing, required: editing && required })
                    .appendTo(field);
            }
            $("<div>", { id: id + "-help", class: "form-text" }).text(description).appendTo(field);
            if (key === "stop") {
                $("<div>", { id: id + "-error", class: "invalid-feedback", role: "alert", hidden: true })
                    .appendTo(field);
            }
        }
        if (editing && activeSection !== "Scenario") {
            $("<button>", { type: "button", class: "btn btn-outline-secondary btn-sm mt-3 remove-row" })
                .text("Remove " + rowLabels[activeSection]).appendTo(group);
        }
        $("#section-fields").append(entry);
        if (activeSection === "Products") renderModeOptions(entry);
        return entry;
    }

    function showEndError(end, text = "") {
        end.toggleClass("is-invalid", Boolean(text)).attr("aria-invalid", String(Boolean(text)));
        message("#" + end.attr("id") + "-error", text);
        if (text) end.closest("details").prop("open", true);
    }

    function pickerDate(value) {
        const clock = "(\\d{2}:\\d{2}(?::\\d{2}(?:\\.\\d{1,3})?)?)";
        const iso = value.match(new RegExp(`^(\\d{4}-\\d{2}-\\d{2})[T ]${clock}Z?$`, "i"));
        if (iso) return iso[1] + "T" + iso[2];
        const spice = value.match(new RegExp(`^(\\d{1,2})-([a-z]{3})-(\\d{4}) +${clock}$`, "i"));
        if (!spice) return "";
        const [, day, month, year, time] = spice;
        const monthNumber = months.findIndex(name => name.toLowerCase() === month.toLowerCase()) + 1;
        if (!monthNumber) return "";
        return `${year}-${String(monthNumber).padStart(2, "0")}-${day.padStart(2, "0")}T${time}`;
    }

    function appendUtcPicker(field, attributes, original) {
        const picker = $("<input>", {
            ...attributes, type: "datetime-local", step: "0.001", class: "form-control", required: true,
        }).val(pickerDate(original)).appendTo(field);
        if (original && !picker.val()) {
            // Keep SPICE formats that a browser calendar cannot represent, such as leap seconds.
            picker.attr("type", "text").val(original);
            return;
        }
        picker.data({ original, initialDate: picker.val() });
    }

    function fieldValue(input) {
        if (input.type !== "datetime-local") return input.value;
        const { original, initialDate } = $(input).data();
        if (input.value === initialDate) return original;
        if (!input.value) return "";
        const [date, time] = input.value.split("T");
        const [year, month, day] = date.split("-");
        return `${day}-${months[Number(month) - 1]}-${year} ${time}`;
    }

    function channels() {
        const entries = currentProject.sections.find(item => item.label === "Instruments")?.rows || [];
        return entries.map(row => row.name);
    }

    function appendChannelSelect(field, attributes, value) {
        const names = channels();
        const selected = value ?? (names.length === 1 ? names[0] : "");
        const select = $("<select>", { ...attributes, class: "form-select" })
            .prop({ disabled: !editing, required: editing }).appendTo(field);
        $("<option>").val("").text("Select an instrument").prop("disabled", true).appendTo(select);
        $("<option>").val("ALL").text("All instruments").appendTo(select);
        for (const name of names.filter(name => name !== "ALL")) {
            $("<option>").val(name).text(name).appendTo(select);
        }
        if (selected && selected !== "ALL" && !names.includes(selected)) {
            $("<option>").val(selected).text(selected + " (unknown instrument)").appendTo(select);
        }
        select.val(selected);
    }

    function appendProductSelect(field, attributes, selected) {
        const select = $("<select>", { ...attributes, class: "form-select" })
            .prop({ disabled: !editing, required: editing }).appendTo(field);
        $("<option>").val("").text("Select a product").prop("disabled", true).appendTo(select);
        for (const name of productNames) {
            $("<option>").val(name).text(name).appendTo(select);
        }
        if (selected && !productNames.includes(selected)) {
            $("<option>").val(selected).text(selected + " (saved value)").appendTo(select);
        }
        select.val(selected);
    }

    function modeOptions(entry) {
        const product = entry.find('[data-key="product"]').val();
        return Object.hasOwn(productModes, product) ? productModes[product] : {};
    }

    function renderModeOptions(entry) {
        const options = modeOptions(entry);
        const product = entry.find('[data-key="product"]').val();
        const selected = entry.find('[data-key="mode"]').val();
        const group = entry.find(".mode-options").empty();
        const codes = new Set([...Object.keys(options), ...selected]);
        for (const code of codes) {
            const row = $("<div>", { class: "mode-choice" }).appendTo(group);
            const label = $("<label>", { class: "form-check mb-0" }).appendTo(row);
            $("<input>", { type: "checkbox", class: "form-check-input mode-toggle" }).val(code)
                .prop({ checked: selected.includes(code), disabled: !editing }).appendTo(label);
            $("<span>", { class: "form-check-label" })
                .text(code + " · " + (options[code] || "Saved code")).appendTo(label);
            const outputs = $("<div>", {
                class: "mode-destinations",
                role: "group",
                "aria-label": "Destinations for " + code,
            }).appendTo(row);
            for (const [destination, name] of [["c", "CSV"], ["s", "Shapefile"]]) {
                const outputLabel = $("<label>", { class: "form-check mb-0" }).appendTo(outputs);
                $("<input>", { type: "checkbox", class: "form-check-input mode-destination" })
                    .val(destination).prop("disabled", !editing).appendTo(outputLabel);
                $("<span>", { class: "form-check-label" }).text(name).appendTo(outputLabel);
            }
            $("<p>", { class: "mode-destination-error small text-danger mb-0", role: "alert", hidden: true })
                .text("Select at least one destination.").appendTo(row);
        }
        if (!codes.size) {
            $("<p>", { class: "text-secondary mb-0" })
                .text(product ? "No mode options available." : "Select a product to see its modes.")
                .appendTo(group);
        }
        syncModeDestinations(entry);
    }

    function syncModeDestinations(entry) {
        const modes = [...entry.find('[data-key="mode"]').val()];
        const signs = entry.find('[data-key="output"]').val();
        entry.find(".mode-choice").each(function () {
            const row = $(this);
            const code = row.find(".mode-toggle").val();
            const selectedSigns = modes.flatMap((mode, index) =>
                mode === code ? [signs[index] || "b"] : []);
            row.find(".mode-destinations").prop("hidden", !selectedSigns.length);
            row.find(".mode-destination-error").prop("hidden", true);
            row.find(".mode-destination").each(function () {
                this.checked = selectedSigns.some(sign => sign === this.value || sign === "b" || /\d/.test(sign));
            });
        });
    }

    function updateMode(entry, codes) {
        const mode = entry.find('[data-key="mode"]');
        const destinations = entry.find('[data-key="output"]');
        const previous = mode.val();
        const signs = destinations.val();
        const remaining = codes.filter(code => previous.includes(code));
        const added = codes.filter(code => !previous.includes(code));
        let next = [...previous].filter(code => remaining.includes(code)).concat(added);
        const product = entry.find('[data-key="product"]').val();
        if (/^corners$/i.test(product) && added.includes("L")) {
            next = ["L", ...next.filter(code => code !== "L")];
        }
        if (signs) {
            const available = [...previous].map((code, index) => ({ code, sign: signs[index] }));
            const defaultSign = /^\d+$/.test(signs) ? "6" : "b";
            destinations.val(next.map(code => {
                const index = available.findIndex(item => item.code === code);
                return (index === -1 ? null : available.splice(index, 1)[0].sign) ?? defaultSign;
            }).join(""));
        }
        mode.val(next.join(""));
    }

    function appendChannelMenu(field, attributes, value) {
        const names = channels();
        const selected = value === undefined
            ? (names.length === 1 ? names : [])
            : value.split(/\s+/).filter(Boolean);
        const dropdown = $("<div>", { class: "dropdown" }).appendTo(field);
        const { id, ...dataAttributes } = attributes;
        const input = $("<input>", { ...dataAttributes, type: "hidden" }).appendTo(dropdown);
        const button = $("<button>", {
            id,
            type: "button",
            class: "btn btn-outline-secondary dropdown-toggle",
            "data-bs-toggle": "dropdown",
            "data-bs-auto-close": "outside",
            "aria-describedby": attributes["aria-describedby"],
            "aria-expanded": "false",
        }).appendTo(dropdown);
        const menu = $("<div>", { class: "dropdown-menu channel-menu p-2" }).appendTo(dropdown);
        for (const name of new Set([...selected, ...names])) {
            const option = $("<label>", { class: "form-check mb-1" }).appendTo(menu);
            $("<input>", { type: "checkbox", class: "form-check-input" }).val(name)
                .prop("checked", selected.includes(name)).appendTo(option);
            $("<span>", { class: "form-check-label" })
                .text(names.includes(name) ? name : name + " (unknown instrument)").appendTo(option);
        }
        if (!menu.children().length) menu.text("Add an instrument in the Instruments tab.");
        function updateSelection() {
            const checked = menu.find(":checked").map((_, option) => option.value).get();
            input.val(checked.join(" "));
            button.text(checked.length ? `${checked.length} selected` : "Select instruments");
        }
        menu.on("change", updateSelection);
        updateSelection();
    }

    function updateSummary(entry) {
        const field = key => {
            const input = entry.find("[data-key]").filter((_, control) => control.dataset.key === key)[0];
            return input ? fieldValue(input).trim() : "";
        };
        const captions = {
            Timeline: () => [field("start"), field("stop")].filter(Boolean).join(" → "),
            Products: () => [field("product"), field("instrument")].filter(Boolean).join(" · "),
            Instruments: () => [field("name"), field("id")].filter(Boolean).join(" · "),
        };
        entry.find(".config-caption").text(captions[activeSection]());
    }

    function updateRows() {
        const groups = $("#section-fields").children();
        groups.each(function (index) {
            if (activeSection === "Scenario") return;
            const label = rowLabels[activeSection] + " " + (index + 1);
            $(this).find(".config-title").text(label);
            updateSummary($(this));
            $(this).find(".remove-row").attr("aria-label", "Remove " + label);
        });
        $("#empty-section").prop("hidden", groups.length > 0);
    }

    function selectProject(project) {
        currentProject = project;
        activeSection = "Timeline";
        editing = false;
        running = false;
        $("#project-name").text(project.name);
        $("#project-path").text(project.id);
        $("#projects button").each(function () {
            const selected = this.dataset.id === project.id;
            $(this).toggleClass("active", selected).attr("aria-pressed", selected);
        });
        $("#empty-project, #run-status").prop("hidden", true);
        $("#overview").prop("hidden", false);
        $("#run-log").empty();
        $("#edit-status").empty();
        renderSection();
        refreshRun();
    }

    async function openProject(id) {
        if (editing || opening) return;
        opening = true;
        updateControls();
        message("#app-error");
        try {
            selectProject(await api("/api/project", "GET", { id }));
        } catch (error) {
            showError("#app-error", error);
        } finally {
            opening = false;
            updateControls();
        }
    }

    async function loadProjectList() {
        const entries = await api("/api/projects", "GET");
        const list = $("#projects").empty();
        const templates = $("#new-template").empty();
        $("<option>").val("").text("Default scenario and channels").appendTo(templates);
        for (const { id, name } of entries) {
            const selected = id === currentProject?.id;
            $("<button>", {
                type: "button",
                class: "list-group-item list-group-item-action",
                "data-id": id,
                "aria-pressed": selected,
            }).text(name).toggleClass("active", selected).appendTo(list);
            $("<option>").val(id).text("Copy " + id).appendTo(templates);
        }
        if (!entries.length) list.text("No projects found.");
        updateControls();
        return entries;
    }

    function renderRun(run) {
        running = run?.state === "Running";
        $("#run-status").prop("hidden", !run);
        if (run) {
            const colors = { Running: "primary", Completed: "success", Failed: "danger" };
            const state = $("#run-state");
            if (state.text() !== run.state) {
                state.attr("class", "badge text-bg-" + colors[run.state]).text(run.state);
            }
            $("#run-output").text(run.output);
            $("#run-log-truncated").prop("hidden", !run.log_truncated);
            const output = run.log || (running ? "Waiting for starter output…" : "No starter output.");
            const log = $("#run-log")[0];
            if (log.textContent !== output) {
                const follow = log.scrollHeight - log.clientHeight - log.scrollTop < 24;
                log.textContent = output;
                if (follow) log.scrollTop = log.scrollHeight;
            }
        }
        updateControls();
    }

    function refreshRun(run) {
        clearTimeout(pollTimer);
        const generation = ++pollGeneration;
        const id = currentProject.id;
        if (run) renderRun(run);

        async function poll() {
            try {
                const latest = await api("/api/run", "GET", { id });
                if (generation !== pollGeneration) return;
                renderRun(latest);
                if (running) pollTimer = setTimeout(poll, 1200);
            } catch (error) {
                if (generation !== pollGeneration) return;
                showError("#app-error", error);
                if (running) pollTimer = setTimeout(poll, 2500);
            }
        }
        poll();
    }

    $("#projects").on("click", "button", function () {
        openProject(this.dataset.id);
    });

    $("#sections").on("click", "button", function () {
        activeSection = this.dataset.section;
        $("#edit-status").empty();
        renderSection();
    });

    $("#edit-section").on("click", () => {
        editing = true;
        $("#edit-status").empty();
        message("#edit-error");
        renderSection(true);
        const entries = $("#section-fields > details");
        if (!entries.filter("[open]").length) entries.first().prop("open", true);
        const first = $("#section-fields :input:visible").first();
        (first.length ? first : $("#add-row")).trigger("focus");
    });

    $("#add-row").on("click", () => {
        const group = appendRow({}, true);
        updateRows();
        group.find(":input:visible").first().trigger("focus");
    });

    $("#section-fields").on("click", ".remove-row", function () {
        const group = $(this).closest("details");
        const adjacent = group.next().length ? group.next() : group.prev();
        group.remove();
        updateRows();
        (adjacent.length ? adjacent.children("summary") : $("#add-row")).trigger("focus");
    });

    $("#section-fields").on("input change", ".config-entry [data-key]", function () {
        const entry = $(this).closest("details");
        if (editing && activeSection === "Timeline" && ["start", "stop"].includes(this.dataset.key)) {
            showEndError(entry.find('[data-key="stop"]'));
        }
        if (editing && activeSection === "Timeline" && this.type === "datetime-local") {
            const end = entry.find('input[type="datetime-local"][data-key="stop"]');
            if (this.dataset.key === "stop") {
                end.removeData("followsStart");
            } else if (!end.val() || end.data("followsStart")) {
                end.val(this.value).data("followsStart", true);
            }
        }
        updateSummary(entry);
    });

    $("#section-fields").on("change", '[data-key="product"]', function () {
        const entry = $(this).closest("details");
        const options = modeOptions(entry);
        const previous = entry.find('[data-key="mode"]').val();
        updateMode(entry, [...new Set(previous)].filter(code => Object.hasOwn(options, code)));
        renderModeOptions(entry);
    }).on("change", ".mode-toggle", function () {
        const entry = $(this).closest("details");
        const codes = entry.find(".mode-toggle:checked").map((_, input) => input.value).get();
        updateMode(entry, codes);
        syncModeDestinations(entry);
    }).on("change", ".mode-destination", function () {
        const row = $(this).closest(".mode-choice");
        const checked = row.find(".mode-destination:checked");
        const error = row.find(".mode-destination-error");
        if (!checked.length) {
            this.checked = true;
            error.prop("hidden", false);
            return;
        }
        error.prop("hidden", true);
        const entry = row.closest("details");
        const output = entry.find('[data-key="output"]');
        const previous = output.val();
        const code = row.find(".mode-toggle").val();
        const sign = checked.length === 2 ? "b" : checked.val();
        const modes = [...entry.find('[data-key="mode"]').val()];
        output.val(modes.map((mode, index) => {
            if (mode === code) return sign;
            return /[csb]/.test(previous[index] || "") ? previous[index] : "b";
        }).join(""));
    });

    $("#editor")[0].addEventListener("invalid", event => {
        const entry = event.target.closest(".config-entry");
        if (entry) entry.open = true;
    }, true);

    $("#cancel-edit").on("click", () => {
        editing = false;
        renderSection(true);
        $("#edit-section").trigger("focus");
    });

    $("#editor").on("submit", async function (event) {
        event.preventDefault();
        if (!editing) return;
        const controls = $(this).find(":input:enabled").prop("disabled", true);
        message("#edit-error");
        let invalidEnd;
        const rows = $("#section-fields fieldset").map(function () {
            const row = {};
            $(this).find("[data-key]").each(function () { row[this.dataset.key] = fieldValue(this); });
            return row;
        }).get();
        try {
            currentProject = await api("/api/project", "PUT", {
                id: currentProject.id,
                section: activeSection,
                revision: section().revision,
                rows,
            });
            editing = false;
            renderSection(true);
            $("#edit-status").text(section().filename + " saved.");
            $("#edit-section").trigger("focus");
        } catch (error) {
            const problem = error.responseJSON;
            if (problem?.field === "stop" && activeSection === "Timeline") {
                invalidEnd = $("#section-fields > details").eq(problem.row - 1).find('[data-key="stop"]');
                showEndError(invalidEnd, problem.error);
            } else {
                showError("#edit-error", error);
            }
        } finally {
            controls.prop("disabled", false);
            invalidEnd?.trigger("focus");
        }
    });

    $("#new-project").on("show.bs.modal", () => {
        $("#new-name").val("");
        $("#new-template").val("");
        message("#create-error");
    }).on("shown.bs.modal", () => $("#new-name").trigger("focus"));

    $("#create-project").on("submit", async function (event) {
        event.preventDefault();
        const submit = $(this).find("[type=submit]").prop("disabled", true);
        message("#create-error");
        try {
            const project = await api("/api/projects", "POST", {
                name: $("#new-name").val().trim(),
                template: $("#new-template").val(),
            });
            bootstrap.Modal.getInstance($("#new-project")[0]).hide();
            selectProject(project);
            try {
                await loadProjectList();
            } catch (error) {
                showError("#app-error", error);
            }
        } catch (error) {
            showError("#create-error", error);
        } finally {
            submit.prop("disabled", false);
        }
    });

    function closeMetakernelBrowser() {
        ++browseGeneration;
        $("#metakernel-browser").prop("hidden", true);
        $("#browse-metakernel").attr("aria-expanded", "false");
    }

    function selectMetakernel(path) {
        ++dropGeneration;
        $("#metakernel-matches").empty().prop("hidden", true);
        $("#metakernel").val(path).trigger("focus");
        message("#metakernel-drop-status");
        closeMetakernelBrowser();
    }

    async function loadMetakernelFolder(directory, fromFile = false) {
        const generation = ++browseGeneration;
        const entries = $("#metakernel-entries");
        const parent = $("#metakernel-parent");
        const status = $("#metakernel-directory");
        message("#metakernel-browser-error");
        status.text("Loading…");
        try {
            const folder = await api("/api/metakernels", "GET", {
                directory,
                ...(fromFile ? { from_file: "1" } : {}),
            });
            if (generation !== browseGeneration) return;
            browseDirectory = folder.directory;
            status.text(folder.directory);
            $("#metakernel-folder-path").val(folder.directory);
            parent.data("directory", folder.parent).prop("disabled", !folder.parent);
            const ancestors = $("#metakernel-ancestors").empty();
            for (const { name, path } of folder.ancestors) {
                $("<button>", {
                    type: "button",
                    class: "btn btn-outline-secondary btn-sm",
                    title: path,
                }).text(name).on("click", () => loadMetakernelFolder(path)).appendTo(ancestors);
            }
            entries.empty();
            for (const [type, items] of [["folder", folder.folders], ["file", folder.files]]) {
                for (const { name, path } of items) {
                    $("<button>", {
                        type: "button",
                        class: "list-group-item list-group-item-action text-break",
                        "data-type": type,
                    }).data("path", path).text(type === "folder" ? name + "/" : name).appendTo(entries);
                }
            }
            if (!entries.children().length) entries.text("No subfolders or .tm files.");
        } catch (error) {
            if (generation !== browseGeneration) return;
            status.text(browseDirectory);
            showError("#metakernel-browser-error", error);
        }
    }

    $("#browse-metakernel").on("click", function () {
        if (!$("#metakernel-browser").prop("hidden")) {
            closeMetakernelBrowser();
            return;
        }
        const selected = $("#metakernel").val().trim();
        $(this).attr("aria-expanded", "true");
        $("#metakernel-browser").prop("hidden", false);
        loadMetakernelFolder(selected, Boolean(selected));
    });
    $("#metakernel-parent").on("click", function () { loadMetakernelFolder($(this).data("directory")); });
    $("#metakernel-home").on("click", () => loadMetakernelFolder("~"));
    $("#metakernel-workspace").on("click", () => loadMetakernelFolder(""));
    $("#metakernel-go").on("click", () => loadMetakernelFolder($("#metakernel-folder-path").val().trim()));
    $("#metakernel-folder-path").on("keydown", event => {
        if (event.key === "Enter") {
            event.preventDefault();
            $("#metakernel-go").trigger("click");
        }
    });
    $("#metakernel-entries").on("click", "button", function () {
        const path = $(this).data("path");
        if (this.dataset.type === "folder") {
            loadMetakernelFolder(path);
        } else {
            selectMetakernel(path);
        }
    });

    $("#metakernel").on("input", () => {
        ++dropGeneration;
        message("#metakernel-drop-status");
        $("#metakernel-matches").empty().prop("hidden", true);
    });

    function showMetakernelMatches(matches, filename) {
        if (matches.length === 1) {
            selectMetakernel(matches[0]);
            message("#metakernel-drop-status", filename + " selected.");
            return;
        }
        if (!matches.length) {
            message("#metakernel-drop-status", "Could not locate " + filename + ". Use Browse to select its folder.");
            if ($("#metakernel-browser").prop("hidden")) $("#browse-metakernel").trigger("click");
            return;
        }
        message("#metakernel-drop-status", "Multiple matching files. Choose the original location.");
        const choices = $("#metakernel-matches").prop("hidden", false);
        for (const path of matches) {
            $("<button>", { type: "button", class: "list-group-item list-group-item-action text-break" })
                .text(path).on("click", () => selectMetakernel(path)).appendTo(choices);
        }
    }

    $("#metakernel-dropzone, #metakernel")
        .on("dragover", function (event) {
            if (!event.originalEvent.dataTransfer.types.includes("Files")) return;
            event.preventDefault();
            event.originalEvent.dataTransfer.dropEffect = "copy";
            $("#metakernel-dropzone").addClass("is-dragging");
        })
        .on("dragleave", () => $("#metakernel-dropzone").removeClass("is-dragging"))
        .on("drop", async function (event) {
            const transfer = event.originalEvent.dataTransfer;
            if (!transfer.types.includes("Files")) return;
            event.preventDefault();
            $("#metakernel-dropzone").removeClass("is-dragging");
            const generation = ++dropGeneration;
            $("#metakernel-matches").empty().prop("hidden", true);
            const [file] = transfer.files;
            if (transfer.files.length !== 1 || !/\.tm$/i.test(file.name) || file.size > 1024 * 1024) {
                message("#metakernel-drop-status", "Drop one .tm file of up to 1 MiB.");
                return;
            }
            message("#metakernel-drop-status", "Looking for " + file.name + "…");
            try {
                const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
                if (generation !== dropGeneration) return;
                const sha256 = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
                const { matches } = await api("/api/metakernels/match", "POST", {
                    name: file.name, size: file.size, sha256, directory: browseDirectory,
                });
                if (generation === dropGeneration) showMetakernelMatches(matches, file.name);
            } catch (error) {
                if (generation === dropGeneration) {
                    message("#metakernel-drop-status", error.responseJSON?.error || "Could not read the dropped file. Use Browse to select it.");
                }
            }
        });

    $("#run-project").on("show.bs.modal", () => {
        $("#run-project-name").text(currentProject.id);
        $("#output-name").val("");
        $("#metakernel").val(typeof runPreferences.metakernel === "string" ? runPreferences.metakernel : "");
        $("#worker-count").val(Number.isSafeInteger(runPreferences.workers) && runPreferences.workers > 0
            ? runPreferences.workers : 1);
        message("#metakernel-drop-status");
        $("#metakernel-matches").empty().prop("hidden", true);
        message("#run-error");
    }).on("shown.bs.modal", () => $("#output-name").trigger("focus"))
        .on("hidden.bs.modal", () => {
            ++dropGeneration;
            closeMetakernelBrowser();
        });

    $("#start-run").on("submit", async function (event) {
        event.preventDefault();
        const submit = $(this).find("[type=submit]").prop("disabled", true);
        const id = currentProject.id;
        message("#run-error");
        const preferences = {
            metakernel: $("#metakernel").val().trim(),
            workers: Number($("#worker-count").val()),
        };
        try {
            const run = await api("/api/run", "POST", {
                id,
                name: $("#output-name").val().trim(),
                ...preferences,
            });
            runPreferences = preferences;
            const dialog = $("#run-project");
            if (id === currentProject.id) {
                refreshRun(run);
                const showConsole = () => {
                    if (id === currentProject.id) $("#run-status")[0].scrollIntoView({ block: "nearest" });
                };
                if (dialog.hasClass("show")) dialog.one("hidden.bs.modal", showConsole);
                else showConsole();
            }
            bootstrap.Modal.getInstance(dialog[0]).hide();
        } catch (error) {
            showError("#run-error", error);
        } finally {
            submit.prop("disabled", false);
        }
    });

    loadProjectList().then(entries => {
        if (entries.length) openProject(entries[0].id);
    }).catch(error => showError("#app-error", error));
});
