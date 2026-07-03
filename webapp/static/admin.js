(() => {
  "use strict";

  const API = "/api/admin";
  const content = document.querySelector("#admin-content");
  const toast = document.querySelector("#admin-toast");
  const actorInput = document.querySelector("#admin-actor");
  const state = {
    config: null,
    key: sessionStorage.getItem("wc26_admin_key") || "",
    actor: sessionStorage.getItem("wc26_admin_actor") || "local-admin",
  };
  actorInput.value = state.actor;

  const flags = {
    Algeria: "alg", Argentina: "arg", Australia: "aus", Austria: "aut", Belgium: "bel", "Bosnia & Herzegovina": "bih", Brazil: "bra", Canada: "can",
    "Cape Verde": "cpv", Colombia: "col", "Costa Rica": "crc", Croatia: "cro", "Côte d'Ivoire": "civ", Curaçao: "cuw",
    Czechia: "cze", Denmark: "den", "DR Congo": "cod", Ecuador: "ecu", Egypt: "egy", England: "eng", France: "fra",
    Germany: "ger", Ghana: "gha", Haiti: "hai", Iran: "irn", Iraq: "irq", Japan: "jpn", Jordan: "jor", Mexico: "mex",
    Morocco: "mar", Netherlands: "ned", "New Zealand": "nzl", Norway: "nor", Panama: "pan", Paraguay: "par", Poland: "pol",
    Portugal: "por", Qatar: "qat", "Saudi Arabia": "ksa", Scotland: "sco", Senegal: "sen", Serbia: "srb", "South Africa": "rsa",
    "South Korea": "kor", Spain: "esp", Sweden: "swe", Switzerland: "sui", Tunisia: "tun", Türkiye: "tur", USA: "usa",
    Uruguay: "uru", Uzbekistan: "uzb", Wales: "wal",
  };
  const teamTranslations = {
    Algeria: "Argélia", Argentina: "Argentina", Australia: "Austrália", Austria: "Áustria", Belgium: "Bélgica",
    "Bosnia & Herzegovina": "Bósnia e Herzegovina", Brazil: "Brasil", Canada: "Canadá", "Cape Verde": "Cabo Verde",
    Colombia: "Colômbia", "Costa Rica": "Costa Rica", Croatia: "Croácia", "Côte d'Ivoire": "Costa do Marfim",
    Curaçao: "Curaçao", Czechia: "Tchéquia", Denmark: "Dinamarca", "DR Congo": "RD Congo", Ecuador: "Equador",
    Egypt: "Egito", England: "Inglaterra", France: "França", Germany: "Alemanha", Ghana: "Gana", Haiti: "Haiti",
    Iran: "Irã", Iraq: "Iraque", Japan: "Japão", Jordan: "Jordânia", Mexico: "México", Morocco: "Marrocos",
    Netherlands: "Holanda", "New Zealand": "Nova Zelândia", Norway: "Noruega", Panama: "Panamá", Paraguay: "Paraguai",
    Poland: "Polônia", Portugal: "Portugal", Qatar: "Catar", "Saudi Arabia": "Arábia Saudita", Scotland: "Escócia",
    Senegal: "Senegal", Serbia: "Sérvia", "South Africa": "África do Sul", "South Korea": "Coreia do Sul",
    Spain: "Espanha", Sweden: "Suécia", Switzerland: "Suíça", Tunisia: "Tunísia", Türkiye: "Turquia",
    USA: "Estados Unidos", Uruguay: "Uruguai", Uzbekistan: "Uzbequistão", Wales: "País de Gales",
  };
  const displayTeamName = value => teamTranslations[value] || value || "Seleção não informada";

  function el(tag, options = {}, children = []) {
    const node = document.createElement(tag);
    Object.entries(options).forEach(([key, value]) => {
      if (value === null || value === undefined) return;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = String(value);
      else if (key.startsWith("data-")) node.setAttribute(key, value);
      else node[key] = value;
    });
    (Array.isArray(children) ? children : [children]).filter(Boolean).forEach(child => node.append(child));
    return node;
  }

  function showToast(message, error = false) {
    toast.textContent = message;
    toast.className = `is-visible${error ? " is-error" : ""}`;
    window.setTimeout(() => { toast.className = ""; }, 3200);
  }

  async function request(path, options = {}, useKey = true) {
    const headers = { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}) };
    if (useKey && state.key) headers["X-Admin-Key"] = state.key;
    if (useKey) headers["X-Admin-Actor"] = state.actor;
    const response = await fetch(`${API}${path}`, { ...options, headers: { ...headers, ...(options.headers || {}) }, cache: "no-store" });
    if (response.status === 401) {
      state.key = "";
      sessionStorage.removeItem("wc26_admin_key");
      renderAuth("A chave informada não foi aceita.");
      throw new Error("Chave administrativa inválida.");
    }
    if (!response.ok) {
      let message = `Falha ${response.status}`;
      try { message = (await response.json()).detail || message; } catch (_) { /* no JSON */ }
      throw new Error(message);
    }
    return response.status === 204 ? null : response.json();
  }

  function navigate(path) {
    history.pushState(null, "", path);
    renderRoute();
  }

  function route() {
    const parts = location.pathname.replace(/^\/admin\/?/, "").split("/").filter(Boolean);
    return { section: parts[0] || "teams", id: parts[1] ? decodeURIComponent(parts[1]) : null };
  }

  function setNavigation(section) {
    document.querySelectorAll("[data-section]").forEach(link => link.classList.toggle("is-active", link.dataset.section === section));
  }

  function pageHeader(title, description, breadcrumb = []) {
    return el("div", {}, [
      breadcrumb.length ? el("div", { class: "breadcrumbs" }, breadcrumb.flatMap((item, index) => [
        item.href ? el("a", { text: item.label, href: item.href, onclick: event => { event.preventDefault(); navigate(item.href); } }) : el("span", { text: item.label }),
        index < breadcrumb.length - 1 ? el("span", { text: "/" }) : null,
      ])) : null,
      el("header", { class: "page-header" }, el("div", {}, [el("h1", { text: title }), el("p", { text: description })])),
    ]);
  }

  function summaryStrip(summary) {
    const definitions = [
      ["Jogadores", summary.players], ["Revisados", summary.reviewed ?? 0],
      ["Pendentes", summary.pending ?? 0], ["Overrides", summary.overrides ?? 0],
    ];
    return el("div", { class: "summary-strip" }, definitions.map(([label, value]) => el("div", {}, [el("span", { text: label }), el("strong", { text: value ?? 0 })])));
  }

  function field(label, control, className = "") {
    return el("label", { class: `field ${className}`.trim() }, [el("span", { text: label }), control]);
  }

  function select(options, value = "") {
    const control = el("select");
    options.forEach(([optionValue, label]) => control.append(el("option", { value: optionValue, text: label })));
    control.value = value || "";
    return control;
  }

  function statusLabel(value) {
    return { reviewed: "Revisado", pending: "Pendente", needs_check: "Precisa revisar", auto_inferred: "Inferido automaticamente", in_progress: "Em andamento" }[value] || value || "Pendente";
  }

  function statusPill(value) {
    return el("span", { class: `status status-${value || "pending"}`, text: statusLabel(value) });
  }

  function flagNode(teamName) {
    const code = flags[teamName];
    return code ? el("img", { class: "flag", src: `/static/flags/${code}.svg`, alt: "" }) : el("span", { class: "avatar", text: String(teamName || "?").slice(0, 2).toUpperCase() });
  }

  function initials(name) {
    return String(name || "?").split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase();
  }

  function avatarNode(player) {
    const avatar = el("span", { class: "avatar", text: initials(player.player_name) });
    const src = player.photo_asset_path ? `/static/${player.photo_asset_path.replace(/^static\//, "")}` : player.photo_url;
    if (src) {
      const image = el("img", { src, alt: player.photo_alt_text || "" });
      image.onerror = () => image.remove();
      avatar.append(image);
    }
    return avatar;
  }

  function table(headers, rows) {
    const body = el("tbody");
    rows.forEach(({ cells, href }) => {
      const row = el("tr", href ? { "data-href": href, tabIndex: 0 } : {} , cells.map(cell => el("td", {}, cell)));
      if (href) {
        row.onclick = () => navigate(href);
        row.onkeydown = event => { if (event.key === "Enter" || event.key === " ") navigate(href); };
      }
      body.append(row);
    });
    return el("div", { class: "table-shell" }, el("table", {}, [
      el("thead", {}, el("tr", {}, headers.map(header => el("th", { text: header })))), body,
    ]));
  }

  function filterToolbar(items, draw, includeTeam = false) {
    const search = el("input", { type: "search", placeholder: "Buscar por nome", autocomplete: "off" });
    const api = select([["", "Todas"], ...state.config.position_groups.map(value => [value, value])]);
    const resolved = select([["", "Todas"], ...state.config.position_roles.map(value => [value, value])]);
    const review = select([["", "Todos"], ...state.config.review_statuses.map(value => [value, statusLabel(value)])]);
    const teamNames = [...new Set(items.map(item => item.team_name).filter(Boolean))].sort((left, right) => displayTeamName(left).localeCompare(displayTeamName(right), "pt-BR"));
    const team = includeTeam ? select([["", "Todas"], ...teamNames.map(value => [value, displayTeamName(value)])]) : null;
    const controls = el("div", { class: "toolbar" }, [
      field("Nome", search), includeTeam ? field("Seleção", team) : null,
      field("Posição API", api), field("Posição resolvida", resolved), field("Status", review),
    ]);
    const apply = () => draw(items.filter(item => {
      const query = search.value.trim().toLocaleLowerCase("pt-BR");
      return (!query || `${item.player_name} ${item.api_player_name || ""}`.toLocaleLowerCase("pt-BR").includes(query))
        && (!api.value || item.api_position_group === api.value)
        && (!resolved.value || item.resolved_position_role === resolved.value)
        && (!review.value || item.review_status === review.value)
        && (!team || !team.value || item.team_name === team.value);
    }));
    [search, api, resolved, review, team].filter(Boolean).forEach(control => control.addEventListener(control === search ? "input" : "change", apply));
    apply();
    return controls;
  }

  function playerRows(players) {
    return players.map(player => ({
      href: `/admin/players/${encodeURIComponent(player.player_id)}`,
      cells: [
        el("div", { class: "entity-cell" }, [avatarNode(player), el("span", {}, [el("strong", { text: player.player_name }), el("small", { text: displayTeamName(player.team_name) })])]),
        player.api_position_group || "—",
        player.inferred_position_role || "—",
        player.manual_position_role || "—",
        el("strong", { text: player.resolved_position_role || "—" }),
        player.resolved_side || "—",
        player.role_confidence || "—",
        statusPill(player.review_status),
      ],
    }));
  }

  async function renderTeams() {
    setNavigation("teams");
    const data = await request("/teams");
    content.replaceChildren(pageHeader("Seleções", "Acompanhe a cobertura de curadoria por elenco."));
    content.append(summaryStrip({ players: data.summary.players, reviewed: data.items.reduce((sum, team) => sum + team.reviewed_players, 0), pending: data.items.reduce((sum, team) => sum + team.pending_players, 0), overrides: data.items.filter(team => team.has_override).length }));
    const search = el("input", { type: "search", placeholder: "Buscar seleção" });
    const status = select([["", "Todos"], ["pending", "Pendente"], ["in_progress", "Em andamento"], ["reviewed", "Revisado"]]);
    const host = el("div");
    const draw = () => {
      const query = search.value.trim().toLocaleLowerCase("pt-BR");
      const rows = data.items.filter(team => (!query || displayTeamName(team.team_name).toLocaleLowerCase("pt-BR").includes(query)) && (!status.value || team.curation_status === status.value));
      host.replaceChildren(table(["Seleção", "Grupo", "Jogadores", "Revisados", "Pendentes", "Curadoria"], rows.map(team => ({
        href: `/admin/teams/${encodeURIComponent(team.team_id)}`,
        cells: [el("div", { class: "entity-cell" }, [flagNode(team.api_team_name || team.team_name), el("strong", { text: displayTeamName(team.team_name) })]), team.group_name || "—", team.players, team.reviewed_players, team.pending_players, statusPill(team.curation_status)],
      }))));
    };
    search.oninput = draw; status.onchange = draw;
    content.append(el("div", { class: "toolbar" }, [field("Seleção", search), field("Status", status)]), host);
    draw();
  }

  async function renderTeam(teamId) {
    setNavigation("teams");
    const data = await request(`/teams/${encodeURIComponent(teamId)}`);
    const team = data.team;
    content.replaceChildren(pageHeader(displayTeamName(team.team_name), "Elenco e status de curadoria da seleção.", [{ label: "Seleções", href: "/admin/teams" }, { label: displayTeamName(team.team_name) }]));
    content.append(summaryStrip(data.summary));
    const host = el("div");
    const controls = filterToolbar(data.players, rows => host.replaceChildren(table(["Jogador", "API", "Inferida", "Manual", "Resolvida", "Lado", "Confiança", "Status"], playerRows(rows))));
    content.append(controls, host, teamOverridePanel(team, data.override));
  }

  function teamOverridePanel(team, override = {}) {
    const name = el("input", { value: override?.display_name_override || "" });
    const shortName = el("input", { value: override?.short_name_override || "" });
    const primary = el("input", { type: "color", value: override?.primary_color || "#55c7b2" });
    const secondary = el("input", { type: "color", value: override?.secondary_color || "#151d28" });
    const flag = el("input", { value: override?.flag_asset_path || "", placeholder: "flags/fra.svg" });
    const review = select(state.config.review_statuses.map(value => [value, statusLabel(value)]), override?.review_status || "pending");
    const notes = el("textarea", { value: override?.status_notes || "" });
    const save = el("button", { class: "primary", text: "Salvar seleção" });
    save.onclick = async () => {
      try {
        await request(`/teams/${encodeURIComponent(team.team_id)}/overrides`, { method: "PUT", body: JSON.stringify({ display_name_override: name.value, short_name_override: shortName.value, primary_color: primary.value, secondary_color: secondary.value, flag_asset_path: flag.value, review_status: review.value, status_notes: notes.value }) });
        showToast("Override da seleção salvo.");
        renderTeam(team.team_id);
      } catch (error) { showToast(error.message, true); }
    };
    return el("section", { class: "section-panel admin-team-panel" }, [
      el("div", { class: "panel-head" }, el("h2", { text: "Override da seleção" })),
      el("div", { class: "form-grid" }, [field("Nome público", name), field("Nome curto", shortName), field("Cor principal", primary), field("Cor secundária", secondary), field("Asset da bandeira", flag), field("Status", review), field("Notas internas", notes, "wide")]),
      el("div", { class: "form-actions" }, save),
    ]);
  }

  async function renderPlayers(overridesOnly = false) {
    setNavigation(overridesOnly ? "position-overrides" : "players");
    const data = await request(overridesOnly ? "/position-overrides" : "/players");
    const title = overridesOnly ? "Overrides de posição" : "Jogadores";
    content.replaceChildren(pageHeader(title, overridesOnly ? "Edições manuais ativas no produto público." : "Revise posições, nomes e ativos dos jogadores."));
    content.append(summaryStrip(data.summary));
    const host = el("div");
    const controls = filterToolbar(data.items, rows => host.replaceChildren(table(["Jogador", "API", "Inferida", "Manual", "Resolvida", "Lado", "Confiança", "Status"], playerRows(rows))), true);
    content.append(controls, host);
  }

  function comparisonItem(label, value) {
    return el("div", { class: "comparison-item" }, [el("span", { text: label }), el("strong", { text: value || "—" })]);
  }

  function photoPreview(player, urlInput, assetInput, altInput) {
    const host = el("div", { class: "photo-preview" });
    const draw = () => {
      const src = assetInput.value.trim() ? `/static/${assetInput.value.trim().replace(/^static\//, "")}` : urlInput.value.trim();
      const fallback = el("div", { class: "photo-fallback", text: initials(player.player_name) });
      host.replaceChildren(fallback);
      if (src) {
        const image = el("img", { src, alt: altInput.value.trim() });
        image.onerror = () => image.remove();
        host.append(image);
      }
    };
    [urlInput, assetInput, altInput].forEach(input => input.addEventListener("input", draw));
    draw();
    return host;
  }

  async function renderPlayer(playerId) {
    setNavigation("players");
    const player = await request(`/players/${encodeURIComponent(playerId)}`);
    content.replaceChildren(pageHeader(player.player_name, `${displayTeamName(player.team_name)} · ${player.resolved_position_role || "Posição não informada"}`, [{ label: "Jogadores", href: "/admin/players" }, { label: player.player_name }]));
    const name = el("input", { value: player.player_name !== player.api_player_name ? player.player_name : "", placeholder: player.api_player_name });
    const group = select([["", "Automático"], ...state.config.position_groups.map(value => [value, value])], player.manual_position_group || "");
    const role = select([["", "Sem override"], ...state.config.position_roles.map(value => [value, value])], player.manual_position_role || "");
    const side = select([["", "Automático"], ...state.config.sides.map(value => [value, value])], player.manual_side || "");
    const secondarySide = select([["", "Não definido"], ...state.config.sides.map(value => [value, value])], player.secondary_side || "");
    const foot = select([["", "Não definido"], ...state.config.dominant_feet.map(value => [value, value])], player.dominant_foot || "");
    const review = select(state.config.review_statuses.map(value => [value, statusLabel(value)]), player.review_status || "pending");
    const notes = el("textarea", { value: player.review_notes || "", placeholder: "Visível somente na área interna" });
    const photoUrl = el("input", { type: "url", value: player.photo_url || "", placeholder: "https://..." });
    const photoAsset = el("input", { value: player.photo_asset_path || "", placeholder: "players/nome.webp" });
    const photoCredit = el("input", { value: player.photo_credit || "" });
    const photoSource = el("input", { type: "url", value: player.photo_source_url || "" });
    const photoAlt = el("input", { value: player.photo_alt_text || "" });
    const checkboxes = state.config.position_roles.map(value => {
      const input = el("input", { type: "checkbox", value, checked: player.manual_secondary_roles.includes(value) });
      return el("label", {}, [input, el("span", { text: value })]);
    });
    const save = el("button", { class: "primary", text: "Salvar alterações" });
    const remove = el("button", { class: "danger", text: "Limpar override", disabled: !player.has_override });
    save.onclick = async () => {
      save.disabled = true;
      try {
        const secondary = checkboxes.map(label => label.querySelector("input")).filter(input => input.checked).map(input => input.value);
        await request(`/players/${encodeURIComponent(playerId)}/overrides`, { method: "PUT", body: JSON.stringify({ display_name_override: name.value, manual_position_group: group.value, manual_position_role: role.value, manual_secondary_roles: secondary, manual_side: side.value, secondary_side: secondarySide.value, dominant_foot: foot.value, review_status: review.value, review_notes: notes.value, photo_url: photoUrl.value, photo_asset_path: photoAsset.value, photo_credit: photoCredit.value, photo_source_url: photoSource.value, photo_alt_text: photoAlt.value }) });
        showToast("Curadoria salva e aplicada ao produto público.");
        renderPlayer(playerId);
      } catch (error) { showToast(error.message, true); }
      finally { save.disabled = false; }
    };
    remove.onclick = async () => {
      if (!window.confirm("Remover o override e voltar à posição inferida?")) return;
      try { await request(`/players/${encodeURIComponent(playerId)}/overrides`, { method: "DELETE" }); showToast("Override removido."); renderPlayer(playerId); }
      catch (error) { showToast(error.message, true); }
    };
    const main = el("section", { class: "editor-main" }, [
      el("div", { class: "readonly-comparison" }, [comparisonItem("API", player.api_position_group), comparisonItem("Inferida", player.inferred_position_role), comparisonItem("Manual", player.manual_position_role), comparisonItem("Resolvida", player.resolved_position_role)]),
      el("div", { class: "panel-head" }, [el("h2", { text: "Dados curados" }), statusPill(player.review_status)]),
      el("div", { class: "form-grid" }, [
        field("Nome público", name), field("Grupo manual", group), field("Posição principal", role), field("Lado principal", side),
        field("Posições secundárias", el("div", { class: "checkbox-grid" }, checkboxes), "wide"), field("Lado secundário", secondarySide), field("Pé dominante", foot),
        field("Status de revisão", review), field("Observações internas", notes, "wide"),
      ]),
      el("div", { class: "form-actions" }, [remove, save]),
    ]);
    const aside = el("aside", { class: "editor-aside" }, [
      photoPreview(player, photoUrl, photoAsset, photoAlt),
      el("div", { class: "panel-head" }, el("h3", { text: "Foto futura" })),
      el("div", { class: "form-grid" }, [field("URL da foto", photoUrl, "wide"), field("Asset local", photoAsset, "wide"), field("Crédito", photoCredit, "wide"), field("Fonte", photoSource, "wide"), field("Texto alternativo", photoAlt, "wide")]),
      el("p", { class: "internal-note", text: "Nenhuma imagem é baixada. Use somente assets próprios ou URLs com licença e crédito conhecidos." }),
    ]);
    content.append(el("div", { class: "editor-layout" }, [main, aside]));
  }

  function renderAuth(message = "Informe a chave configurada para esta área.") {
    content.setAttribute("aria-busy", "false");
    const input = el("input", { type: "password", autocomplete: "current-password", placeholder: "Chave administrativa" });
    const form = el("form", {}, [field("Chave", input), el("button", { type: "submit", class: "primary", text: "Entrar" })]);
    form.onsubmit = event => { event.preventDefault(); state.key = input.value; sessionStorage.setItem("wc26_admin_key", state.key); renderRoute(); };
    content.replaceChildren(el("section", { class: "auth-panel" }, [el("h1", { text: "Acesso interno" }), el("p", { text: message }), form]));
    input.focus();
  }

  async function renderRoute() {
    if (state.config?.requires_key && !state.key) { renderAuth(); return; }
    const current = route();
    content.setAttribute("aria-busy", "true");
    content.replaceChildren(el("p", { class: "loading", text: "Carregando curadoria..." }));
    try {
      if (current.section === "teams" && current.id) await renderTeam(current.id);
      else if (current.section === "players" && current.id) await renderPlayer(current.id);
      else if (current.section === "players") await renderPlayers(false);
      else if (current.section === "position-overrides") await renderPlayers(true);
      else await renderTeams();
      document.title = "Curadoria · World Cup Analytics";
      content.focus({ preventScroll: true });
    } catch (error) {
      if (!content.querySelector(".auth-panel")) content.replaceChildren(el("section", { class: "empty" }, [el("strong", { text: "Não foi possível abrir esta área." }), el("p", { text: error.message })]));
    } finally { content.setAttribute("aria-busy", "false"); }
  }

  document.addEventListener("click", event => {
    const link = event.target.closest("[data-admin-link]");
    if (!link) return;
    event.preventDefault();
    navigate(link.getAttribute("href"));
  });
  actorInput.addEventListener("change", () => {
    state.actor = actorInput.value.trim() || "local-admin";
    sessionStorage.setItem("wc26_admin_actor", state.actor);
  });
  window.addEventListener("popstate", renderRoute);

  request("/config", {}, false)
    .then(config => { state.config = config; renderRoute(); })
    .catch(error => content.replaceChildren(el("section", { class: "empty" }, [el("strong", { text: "Área administrativa indisponível." }), el("p", { text: error.message })])));
})();
