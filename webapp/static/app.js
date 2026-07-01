(() => {
  "use strict";

  const API = "/api";
  const DEFAULT_YEAR = "2026";
  const DEFAULT_PAGE = "overview";
  const commonMenus = [
    { id: "overview", label: "Início" },
    { id: "competition", label: "Competição" },
    { id: "matches", label: "Partidas" },
    { id: "players", label: "Jogadores" },
    { id: "teams", label: "Países" },
  ];
  const menuAliases = {
    overview: "overview", inicio: "overview", home: "overview", visao_geral: "overview", competition: "competition",
    competicao: "competition", teams: "teams", times: "teams", paises: "teams",
    países: "teams", selecoes: "teams", seleções: "teams", players: "players",
    jogadores: "players", matches: "matches", partidas: "matches",
    official_metrics: "official-metrics", "official-metrics": "official-metrics",
    estatisticas_oficiais: "official-metrics", shots: "shots", finalizacoes: "shots",
    thestatsapi_match: "thestatsapi_match", "thestatsapi-match": "thestatsapi_match",
    jogo_base: "thestatsapi_match", abertura: "thestatsapi_match",
    xg: "xg", availability: "availability", disponibilidade: "availability",
    history: "history", historico: "history",
  };
  const menuLabels = {
    overview: "Início", competition: "Competição", teams: "Países",
    players: "Jogadores", matches: "Partidas", "official-metrics": "Métricas oficiais",
    thestatsapi_match: "Jogo base", shots: "Finalizações e xG", availability: "Disponibilidade",
  };
  const endpointFor = {
    overview: "overview", competition: "competition", teams: "teams",
    players: "players", matches: "matches", "official-metrics": "official-metrics",
    thestatsapi_match: "thestatsapi-match", shots: "shots", availability: "availability",
  };

  const state = {
    editions: [],
    year: DEFAULT_YEAR,
    page: DEFAULT_PAGE,
    detailId: null,
    edition: null,
    controller: null,
    cache: new Map(),
    pathname: location.pathname,
    matchPlayers: [],
    competitionData: null,
    quickView: null,
    statPopover: null,
  };

  const els = {
    view: document.querySelector("#view"),
    select: document.querySelector("#edition-select"),
    nav: document.querySelector("#primary-nav"),
    coverage: document.querySelector("#coverage-text"),
    footerSource: document.querySelector("#footer-source"),
    menuButton: document.querySelector("#menu-toggle"),
    loading: document.querySelector("#loading-template"),
  };

  const text = value => value === null || value === undefined || value === "" ? "—" : String(value);
  const label = key => String(key).replace(/[_-]+/g, " ").replace(/\b\w/g, char => char.toUpperCase());
  const normalizeId = value => menuAliases[String(value || "").toLowerCase().replace(/\s+/g, "_")] || String(value || "").toLowerCase();
  const isObject = value => value && typeof value === "object" && !Array.isArray(value);
  const entries = value => isObject(value) ? Object.entries(value) : [];
  const number = value => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const first = (object, keys, fallback = null) => keys.find(key => object?.[key] !== undefined) ? object[keys.find(key => object?.[key] !== undefined)] : fallback;
  const listFrom = (data, keys = []) => {
    if (Array.isArray(data)) return data;
    for (const key of keys) if (Array.isArray(data?.[key])) return data[key];
    return [];
  };
  const technicalKeyPattern = /(^|_)(id|source|endpoint|fetch|raw|hash|coverage|available|status|provider|competition|season)(_|$)|thestatsapi|statsbomb|api/i;
  const technicalTextPattern = /TheStats|StatsBomb|FIFA PDF|coverage|cobertura|endpoint|ingest|materializ|fonte|source|raw|hash|status técnico/i;

  function node(tag, options = {}, children = []) {
    const element = document.createElement(tag);
    Object.entries(options).forEach(([key, value]) => {
      if (value === null || value === undefined) return;
      if (key === "class") element.className = value;
      else if (key === "text") element.textContent = text(value);
      else if (key === "style") element.style.cssText = value;
      else if (key.startsWith("aria-") || key.startsWith("data-") || key === "role") element.setAttribute(key, value);
      else element[key] = value;
    });
    (Array.isArray(children) ? children : [children]).filter(Boolean).forEach(child => element.append(child));
    return element;
  }

  async function getJSON(path, { refresh = false } = {}) {
    const response = await fetch(`${API}${path}`, {
      signal: state.controller?.signal,
      cache: "no-store",
      headers: { Accept: "application/json", "Cache-Control": "no-cache" },
    });
    if (!response.ok) {
      let detail = "";
      try { detail = first(await response.json(), ["detail", "message"], ""); } catch (_) { /* response has no JSON */ }
      throw new Error(detail || `A API respondeu com status ${response.status}.`);
    }
    const data = await response.json();
    return data;
  }

  function parseRoute() {
    const legacy = location.hash.startsWith("#/")
      ? location.hash.replace(/^#\/?/, "").split("/").filter(Boolean)
      : [];
    const parts = legacy.length ? legacy : location.pathname.replace(/^\/+/, "").split("/").filter(Boolean);
    if (parts[0] === "history" || parts[0] === "historico") {
      return { year: state.year || DEFAULT_YEAR, page: "history", detailId: null };
    }
    return {
      year: parts[0] || state.year || DEFAULT_YEAR,
      page: normalizeId(parts[1] || DEFAULT_PAGE),
      detailId: parts[2] ? decodeURIComponent(parts.slice(2).join("/")) : null,
    };
  }

  function scrollToInternalAnchor() {
    if (!location.hash || location.hash.startsWith("#/")) return;
    let id = location.hash.slice(1);
    try { id = decodeURIComponent(id); } catch (_) { /* keep the literal hash */ }
    document.getElementById(id)?.scrollIntoView({ block: "start" });
  }

  function editionYear(item) { return String(first(item, ["year", "edition", "edition_year", "id"], "")); }
  function editionCoverage(item) {
    const value = first(item, ["coverage_label", "coverage_level", "data_coverage_level", "level", "status", "coverage"], "Cobertura não informada");
    const resolved = isObject(value) ? first(value, ["label", "level", "status"], "Cobertura não informada") : value;
    if (typeof resolved === "string" && /partial|parcial|sample|amostra/i.test(resolved)) return "Acervo parcial";
    if (typeof resolved === "string" && /complete|completa/i.test(resolved)) return "Acervo completo";
    return "Acervo disponível";
  }

  function editionMenus(item) {
    const raw = first(item, ["menus", "navigation", "pages", "available_views"], []);
    let menus = Array.isArray(raw) ? raw.map(entry => isObject(entry)
      ? { id: normalizeId(first(entry, ["id", "slug", "key", "path"])), label: first(entry, ["label", "name", "title"]) }
      : { id: normalizeId(entry), label: menuLabels[normalizeId(entry)] }
    ) : [];
    if (!menus.length) menus = [...commonMenus];
    const capabilities = first(item, ["capabilities", "features"], {});
    const caps = Array.isArray(capabilities)
      ? capabilities.map(normalizeId)
      : entries(capabilities).filter(([, enabled]) => Boolean(enabled)).map(([key]) => normalizeId(key));
    caps.forEach(id => {
      if (menuLabels[id] && !menus.some(menu => menu.id === id)) menus.push({ id, label: menuLabels[id] });
    });
    const public2026Menus = new Set(commonMenus.map(menu => menu.id));
    return menus
      .filter(menu => menu.id && endpointFor[menu.id] && menu.id !== "availability" && menu.id !== "thestatsapi_match")
      .filter(menu => editionYear(item) !== DEFAULT_YEAR || public2026Menus.has(menu.id))
      .map(menu => ({ ...menu, label: menu.label || menuLabels[menu.id] || label(menu.id) }));
  }

  function routePath(year = state.year, page = DEFAULT_PAGE, id = null) {
    if (page === "history") return "/history";
    if (page === "overview") return `/${year || DEFAULT_YEAR}`;
    const parts = [year || DEFAULT_YEAR, page || DEFAULT_PAGE];
    if (id) parts.push(encodeURIComponent(id));
    return `/${parts.join("/")}`;
  }

  function goTo(year, page, id = null, { replace = false } = {}) {
    const path = routePath(year, page, id);
    if (replace) history.replaceState(null, "", path);
    else history.pushState(null, "", path);
    navigate();
  }

  function setSkin(page, year) {
    document.body.classList.remove("is-match-center");
    document.body.dataset.page = page;
    document.body.dataset.skin = page === "history" ? "history" : year === "2022" ? "2022" : year === "2026" ? "2026" : "history";
  }

  function renderCatalog() {
    els.select.replaceChildren();
    state.editions.forEach(edition => {
      const year = editionYear(edition);
      els.select.append(node("option", { value: year, text: year }));
    });
    if (!state.editions.some(item => editionYear(item) === state.year)) {
      els.select.append(node("option", { value: state.year, text: state.year }));
    }
    els.select.value = state.year;
    state.edition = state.editions.find(item => editionYear(item) === state.year) || null;
    const coverage = state.edition ? editionCoverage(state.edition) : "Acervo em preparação";
    els.coverage.textContent = state.year === DEFAULT_YEAR
      ? `Central analítica da Copa do Mundo ${state.year}`
      : `Arquivo da Copa do Mundo ${state.year} · ${coverage}`;
    els.footerSource.textContent = "Créditos e fontes consolidados na documentação do projeto.";
    renderNav();
  }

  function renderNav() {
    const menus = editionMenus(state.edition || {});
    const links = menus.map(menu => {
      const active = state.page === menu.id;
      return node("a", {
        class: "nav-link", href: routePath(state.year, menu.id), text: menu.label,
        ...(active ? { "aria-current": "page" } : {}),
      });
    });
    links.push(node("a", {
      class: "nav-link mobile-history-link", href: "/history", text: "Arquivo histórico",
      ...(state.page === "history" ? { "aria-current": "page" } : {}),
    }));
    els.nav.replaceChildren(...links);
  }

  function showLoading() {
    els.view.setAttribute("aria-busy", "true");
    els.view.replaceChildren(els.loading.content.cloneNode(true));
  }

  function pageHead(kicker, title, description) {
    return node("header", { class: "page-head" }, [
      node("div", {}, [node("p", { class: "eyebrow", text: kicker }), node("h1", { text: title })]),
      node("p", { class: "dek", text: description }),
    ]);
  }

  function metricGrid(data) {
    const preferred = first(data, ["metrics", "summary", "totals", "kpis"], data);
    const values = entries(preferred).filter(([, value]) => ["string", "number", "boolean"].includes(typeof value)).slice(0, 8);
    if (!values.length) return null;
    return node("div", { class: "metric-grid" }, values.map(([key, value]) =>
      node("article", { class: "metric" }, [
        node("span", { class: "metric-label", text: label(key) }),
        node("strong", {
          class: "metric-value",
          text: /year|edition/i.test(key) ? text(value) : formatValue(value),
        }),
      ])
    ));
  }

  function formatValue(value) {
    if (typeof value === "number") return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(value);
    if (typeof value === "boolean") return value ? "Sim" : "Não";
    return text(value);
  }

  const metricNames = {
    matches: "Partidas", finished: "Jogos encerrados", goals: "Gols", teams: "Seleções", champion: "Campeã",
    goals_per_match: "Gols por jogo", players: "Jogadores", shots: "Finalizações",
    shots_on_target: "No alvo", shot_accuracy: "Precisão", xg: "xG",
    total_shots: "Finalizações", accurate_passes: "Passes certos",
    total_passes: "Passes", ball_recoveries: "Recuperações",
    duels_won_percentage: "Duelos ganhos", dribbles_percentage: "Dribles certos",
    big_chances_missed: "Grandes chances perdidas", saves: "Defesas",
    expected_goals: "Gols esperados", goals_minus_xg: "Gols − xG",
    attempts_at_goal: "Tentativas", attempts_on_target: "Tentativas no alvo",
    pass_completion_pct: "Passes certos", passes_completed: "Passes completos",
    passes_complete: "Passes completos", total_distance_km: "Distância total",
    total_distance_m: "Distância total", top_speed_kmh: "Velocidade máxima",
    tackles_won: "Desarmes ganhos", possession_regains: "Recuperações",
    fouled_in_final_third: "Faltas sofridas no terço final", offsides: "Impedimentos",
    touches_in_penalty_area: "Toques na área", clearances: "Cortes",
    interceptions: "Interceptações", tackles: "Desarmes",
    tackles_won_percentage: "Aproveitamento dos desarmes",
    aerial_duels_percentage: "Duelos aéreos ganhos", dispossessed: "Perdas de posse",
    ground_duels_percentage: "Duelos pelo chão ganhos", goal_kicks: "Tiros de meta",
    goals_prevented: "Gols evitados", high_claims: "Bolas altas defendidas",
    ball_possession: "Posse de bola", big_chances: "Grandes chances",
    corner_kicks: "Escanteios", fouls: "Faltas", free_kicks: "Tiros livres",
    goalkeeper_saves: "Defesas do goleiro", passes: "Passes",
    red_cards: "Cartões vermelhos", yellow_cards: "Cartões amarelos",
    accurate_crosses: "Cruzamentos certos", accurate_long_balls: "Bolas longas certas",
    final_third_entries: "Entradas no terço final", throw_ins: "Laterais",
    blocked_shots: "Chutes bloqueados", hit_woodwork: "Bolas na trave",
    shots_inside_box: "Chutes dentro da área", shots_off_target: "Chutes para fora",
    shots_outside_box: "Chutes fora da área",
  };
  const metricName = key => metricNames[key] || label(key);
  const EVENT_LABELS = {
    goal: "Gol",
    shot_on_target: "Chute no alvo",
    shot_off_target: "Chute para fora",
    shot_blocked: "Chute bloqueado",
    foul: "Falta",
    yellow_card: "Cartão amarelo",
    red_card: "Cartão vermelho",
    substitution: "Substituição",
    corner_kick: "Escanteio",
    offside: "Impedimento",
    var: "VAR",
    added_time: "Acréscimos",
    period_start: "Início do período",
    period_end: "Fim do período",
    penalty: "Pênalti",
  };
  const EVENT_ICONS = {
    goal: "●", penalty: "●", shot_on_target: "◎", shot_off_target: "○",
    shot_blocked: "×", foul: "!", yellow_card: "■", red_card: "■",
    substitution: "⇄", corner_kick: "⚑", offside: "↥", var: "◇",
    added_time: "+", period_start: "▶", period_end: "■",
  };
  const NARRATIVE_EVENT_TYPES = new Set([
    "goal", "penalty", "var", "red_card", "yellow_card", "substitution", "shot_on_target",
  ]);
  const RADAR_LABELS = {
    Ata: "Ataque", Ataque: "Ataque",
    Cri: "Criação", Criação: "Criação",
    Pas: "Passe", Passe: "Passe",
    Def: "Defesa", Defesa: "Defesa",
    Duelos: "Duelos",
    Par: "Participação", Participação: "Participação",
    Progressão: "Progressão", Pressão: "Pressão",
    "Defesa do gol": "Defesa do gol", Distribuição: "Distribuição",
    "Passe longo": "Passe longo", "Participação com bola": "Participação com bola",
    "Ações fora da área": "Ações fora da área", "Pressão sofrida": "Pressão sofrida",
  };
  const personName = item => first(item, ["player_name", "name", "label"], item?.team_name ? teamName(item) : "Não informado");
  const POSITION_CODES = {
    g: "GOL", gk: "GOL", gol: "GOL", goalkeeper: "GOL", goleiro: "GOL",
    d: "DEF", df: "DEF", def: "DEF", defender: "DEF", defesa: "DEF", zagueiro: "DEF", lateral: "DEF",
    m: "MEI", mf: "MEI", mei: "MEI", midfielder: "MEI", meio: "MEI", meio_campo: "MEI", volante: "MEI",
    f: "ATA", fw: "ATA", ata: "ATA", forward: "ATA", atacante: "ATA", ponta: "ATA", centroavante: "ATA",
  };

  function positionLabel(value) {
    if (!value) return "—";
    const normalized = String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim().replace(/[\s-]+/g, "_");
    if (POSITION_CODES[normalized]) return POSITION_CODES[normalized];
    const prefix = Object.keys(POSITION_CODES).find(key => normalized.startsWith(`${key}_`));
    return prefix ? POSITION_CODES[prefix] : String(value).slice(0, 3).toUpperCase();
  }
  const countryMeta = {
    "Algeria": ["Argélia", "alg"], "Argentina": ["Argentina", "arg"], "Australia": ["Austrália", "aus"],
    "Austria": ["Áustria", "aut"], "Belgium": ["Bélgica", "bel"], "Bosnia & Herzegovina": ["Bósnia e Herzegovina", "bih"],
    "Brazil": ["Brasil", "bra"], "Canada": ["Canadá", "can"], "Cape Verde": ["Cabo Verde", "cpv"],
    "Colombia": ["Colômbia", "col"], "Croatia": ["Croácia", "cro"], "Curaçao": ["Curaçao", "cuw"], "Czechia": ["Tchéquia", "cze"],
    "Côte d'Ivoire": ["Costa do Marfim", "civ"], "DR Congo": ["RD Congo", "cod"], "Ecuador": ["Equador", "ecu"],
    "Egypt": ["Egito", "egy"], "England": ["Inglaterra", "eng"], "France": ["França", "fra"],
    "Germany": ["Alemanha", "ger"], "Ghana": ["Gana", "gha"], "Haiti": ["Haiti", "hai"],
    "Iran": ["Irã", "irn"], "Iraq": ["Iraque", "irq"], "Japan": ["Japão", "jpn"],
    "Jordan": ["Jordânia", "jor"], "Mexico": ["México", "mex"], "Morocco": ["Marrocos", "mar"],
    "Netherlands": ["Holanda", "ned"], "New Zealand": ["Nova Zelândia", "nzl"], "Norway": ["Noruega", "nor"],
    "Panama": ["Panamá", "pan"], "Paraguay": ["Paraguai", "par"], "Portugal": ["Portugal", "por"],
    "Qatar": ["Catar", "qat"], "Saudi Arabia": ["Arábia Saudita", "ksa"], "Scotland": ["Escócia", "sco"],
    "Senegal": ["Senegal", "sen"], "South Africa": ["África do Sul", "rsa"], "South Korea": ["Coreia do Sul", "kor"],
    "Spain": ["Espanha", "esp"], "Sweden": ["Suécia", "swe"], "Switzerland": ["Suíça", "sui"],
    "Tunisia": ["Tunísia", "tun"], "Türkiye": ["Turquia", "tur"], "Turkey": ["Turquia", "tur"],
    "USA": ["Estados Unidos", "usa"], "United States": ["Estados Unidos", "usa"], "Uruguay": ["Uruguai", "uru"],
    "Uzbekistan": ["Uzbequistão", "uzb"], "Costa Rica": ["Costa Rica", "crc"], "Denmark": ["Dinamarca", "den"],
    "Poland": ["Polônia", "pol"], "Serbia": ["Sérvia", "srb"], "Cameroon": ["Camarões", "cmr"], "Wales": ["País de Gales", "wal"],
  };
  const availableFlagCodes = new Set(["alg", "arg", "aus", "aut", "bel", "bih", "bra", "can", "civ", "cmr", "cod", "col", "cpv", "crc", "cro", "cuw", "cze", "den", "ecu", "egy", "eng", "esp", "fra", "ger", "gha", "hai", "irn", "irq", "jor", "jpn", "kor", "ksa", "mar", "mex", "ned", "nor", "nzl", "pan", "par", "pol", "por", "qat", "rsa", "sco", "sen", "srb", "sui", "swe", "tun", "tur", "uru", "usa", "uzb", "wal"]);
  const teamColors = {
    alg: "#148b4f", arg: "#74c8f0", aus: "#f7c948", aut: "#ef4444", bel: "#facc15",
    bih: "#2563eb", bra: "#f7df32", can: "#ef233c", civ: "#f97316", cmr: "#16a34a",
    cod: "#38bdf8", col: "#facc15", cpv: "#2563eb", crc: "#ef4444", cro: "#dc2626",
    cuw: "#2563eb", cze: "#1d4ed8", den: "#ef4444", ecu: "#facc15", egy: "#ef4444",
    eng: "#ffffff", esp: "#ef4444", fra: "#2563eb", ger: "#facc15", gha: "#16a34a",
    hai: "#2563eb", irn: "#22c55e", irq: "#ef4444", jor: "#16a34a", jpn: "#f8fafc",
    kor: "#ef4444", ksa: "#16a34a", mar: "#dc2626", mex: "#16a34a", ned: "#f97316",
    nor: "#2563eb", nzl: "#1e3a8a", pan: "#ef4444", par: "#2563eb", pol: "#f8fafc",
    por: "#22c55e", qat: "#7f1d46", rsa: "#facc15", sco: "#2563eb", sen: "#16a34a",
    srb: "#ef4444", sui: "#ef4444", swe: "#facc15", tun: "#ef4444", tur: "#ef4444",
    uru: "#60a5fa", usa: "#2563eb", uzb: "#38bdf8", wal: "#22c55e",
  };
  const rawTeamName = item => first(item, ["team_name", "name", "label"], "Não informado");
  const displayTeamName = value => countryMeta[value]?.[0] || value || "Não informado";
  const teamCode = value => countryMeta[value]?.[1] || String(value || "tbd").slice(0, 3).toLowerCase();
  const teamName = item => displayTeamName(rawTeamName(item));
  const translateTeamsInText = value => {
    let result = text(value);
    Object.keys(countryMeta).sort((a, b) => b.length - a.length).forEach(name => {
      result = result.replaceAll(name, displayTeamName(name));
    });
    return result;
  };

  function flagNode(team, className = "flag-mini") {
    const name = typeof team === "string" ? team : rawTeamName(team);
    const code = teamCode(name);
    const translated = displayTeamName(name);
    if (availableFlagCodes.has(code)) {
      return node("img", { class: className, src: `/static/flags/${code}.svg`, alt: `Bandeira de ${translated}`, loading: "lazy" });
    }
    return node("span", { class: `${className} flag-fallback`, text: code.toUpperCase(), "aria-label": `Bandeira indisponível: ${translated}` });
  }

  function teamLabel(team, className = "team-label") {
    const name = typeof team === "string" ? team : rawTeamName(team);
    return node("span", { class: className, title: displayTeamName(name) }, [
      flagNode(name),
      node("span", { text: displayTeamName(name) }),
    ]);
  }

  function teamColor(team, fallbackIndex = 0) {
    return teamColors[teamCode(team)] || ["#66ffd7", "#ff3c1f", "#c8ff1d", "#2167ff"][fallbackIndex % 4];
  }

  function matchPalette(home, away) {
    return `--home-color:${teamColor(home, 0)};--away-color:${teamColor(away, 1)};`;
  }

  function formatMatchDate(value) {
    if (!value) return "Data não informada";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Data não informada";
    return new Intl.DateTimeFormat("pt-BR", {
      timeZone: "America/Sao_Paulo",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date).replace(",", ",");
  }

  function minuteLabel(goal) {
    return `${formatValue(goal.minute)}${goal.extra_time ? `+${goal.extra_time}` : ""}'`;
  }

  function section(title, meta, content, className = "", id = null) {
    return node("section", { class: `section ${className}`.trim(), id }, [
      node("div", { class: "section-heading" }, [
        node("h2", { text: title }),
        meta ? node("span", { text: meta }) : null,
      ]),
      content,
    ]);
  }

  function kpis(summary, keys = Object.keys(summary || {})) {
    const values = keys.filter(key => summary?.[key] !== undefined && summary[key] !== null);
    if (!values.length) return null;
    return node("div", { class: "metric-grid" }, values.map(key =>
      node("article", { class: "metric" }, [
        node("span", { class: "metric-label", text: metricName(key) }),
        node("strong", { class: "metric-value", text: formatValue(summary[key]) }),
      ])
    ));
  }

  function horizontalBars(rows, metric, { name = personName, limit = 10, unit = "" } = {}) {
    const clean = rows
      .map(item => ({ item, value: number(item?.[metric]) }))
      .filter(item => item.value !== null)
      .slice(0, limit);
    if (!clean.length) return emptyState(`Sem dados para ${metricName(metric)}`, "Esta métrica não está disponível no recorte selecionado.");
    const max = Math.max(...clean.map(item => Math.abs(item.value)), 1);
    return node("ol", { class: "bar-chart", "aria-label": `Ranking de ${metricName(metric)}` }, clean.map(({ item, value }, index) => {
      const tooltip = `${metricName(metric)} · ${name(item)}: ${formatValue(value)}${unit}`;
      const row = node("li", { class: "bar-row", tabIndex: 0, "aria-label": tooltip }, [
        node("span", { class: "bar-rank", text: index + 1 }),
        node("span", { class: "bar-name", text: name(item) }),
        node("span", { class: "bar-track", "aria-hidden": "true" }, node("span", {
          class: "bar-fill",
          style: `--bar-size:${Math.max(2, Math.abs(value) / max * 100)}%`,
          title: `${formatValue(value)}${unit}`,
        })),
        node("strong", { class: "bar-value", text: `${formatValue(value)}${unit}` }),
      ]);
      return attachChartTooltip(row, tooltip);
    }));
  }

  function rankingPanels(rankings, { entity = "team", maxPanels = 4, valueKey = null } = {}) {
    const panels = entries(rankings).filter(([, rows]) => Array.isArray(rows) && rows.length).slice(0, maxPanels);
    if (!panels.length) return null;
    return node("div", { class: "chart-grid" }, panels.map(([metric, rows]) =>
      node("article", { class: "chart-card" }, [
        node("div", { class: "chart-card-head" }, [
          node("p", { class: "eyebrow", text: "Ranking" }),
          node("h3", { text: metricName(metric) }),
        ]),
        horizontalBars(rows, valueKey || metric, { name: entity === "player" ? personName : teamName, limit: 8 }),
      ])
    ));
  }

  function scoreCard(match, { hero = false } = {}) {
    const home = first(match, ["home_team"], "Mandante");
    const away = first(match, ["away_team"], "Visitante");
    const stage = first(match, ["competition_stage", "group_name", "stage"], "Partida");
    const stageLabel = /^[A-Z]$/i.test(String(stage)) ? `Grupo ${stage}` : stage;
    const date = first(match, ["match_date", "date"], null);
    const goals = Array.isArray(match?.goals) ? match.goals : [];
    const stadium = first(match, ["stadium", "venue"], null);
    const venueCity = first(match, ["venue_city"], null);
    const stadiumLabel = stadium && venueCity ? `${stadium} · ${venueCity}` : stadium;
    const referee = first(match, ["referee", "main_referee"], null);
    const detailRows = [
      !hero ? ["Data", formatMatchDate(date)] : null,
      stadiumLabel ? ["Estádio", stadiumLabel] : null,
      referee ? ["Árbitro", referee] : null,
    ].filter(Boolean);
    return node("article", { class: `score-card${hero ? " match-score-card" : ""}`, style: matchPalette(home, away) }, [
      node("div", { class: "score-meta" }, [
        node("span", { text: stageLabel }),
        node("time", { dateTime: date || "", text: formatMatchDate(date).replace(", ", " · ") }),
      ]),
      node("div", { class: "score-line" }, [
        node("strong", {}, teamLabel(home)),
        node("span", { class: "score", text: `${formatValue(match?.home_score)} : ${formatValue(match?.away_score)}`, "aria-label": `${displayTeamName(home)} ${formatValue(match?.home_score)}, ${displayTeamName(away)} ${formatValue(match?.away_score)}` }),
        node("strong", {}, teamLabel(away)),
      ]),
      goals.length ? node("ol", { class: "score-goals", "aria-label": "Gols da partida" }, goals.map(goal => node("li", {
        class: goal.team_name === away ? "away" : "home",
      }, [
        node("span", { class: "goal-minute", text: minuteLabel(goal) }),
        node("span", { text: personName(goal) }),
      ]))) : node("p", { class: "score-venue", text: "Gols não informados" }),
      node("dl", { class: `score-details${hero ? " score-details-compact" : ""}` }, detailRows.map(([key, value]) =>
        node("div", {}, [node("dt", { text: key }), node("dd", { text: value })])
      )),
    ]);
  }

  function routeTo(page, id) {
    if (!id) return;
    goTo(state.year, page, id);
  }

  function detailAction(labelText, page, id) {
    if (!id) return null;
    return node("button", {
      type: "button",
      class: "action-link",
      text: labelText,
      onclick: event => {
        event.stopPropagation();
        routeTo(page, id);
      },
    });
  }

  function clickableCard(card, page, id) {
    if (!id) return card;
    card.classList.add("clickable-card");
    card.tabIndex = 0;
    card.setAttribute("role", "link");
    card.addEventListener("click", () => routeTo(page, id));
    card.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        routeTo(page, id);
      }
    });
    return card;
  }

  function matchCard(match) {
    const card = clickableCard(scoreCard(match), "matches", match?.match_id);
    if (match?.match_id) card.append(detailAction("Abrir partida", "matches", match.match_id));
    return card;
  }

  function entityCard(item, { page, idKey, title, kicker = "Registro", metrics = [] }) {
    const id = item?.[idKey];
    const rows = metrics
      .filter(key => item?.[key] !== undefined && item?.[key] !== null)
      .slice(0, 6);
    const card = node("article", { class: "card entity-card" }, [
      node("span", { class: "card-kicker", text: kicker }),
      node("h3", {}, page === "teams" ? teamLabel(rawTeamName(item)) : title(item)),
      rows.length ? node("dl", { class: "data-list" }, rows.map(key =>
        node("div", { class: "data-row" }, [
          node("dt", { text: metricName(key) }),
          node("dd", { text: formatValue(item[key]) }),
        ])
      )) : null,
      detailAction("Abrir perfil", page, id),
    ]);
    return clickableCard(card, page, id);
  }

  function scatterPlot(rows) {
    const clean = rows.map(item => ({ item, x: number(item?.xg), y: number(item?.goals) }))
      .filter(point => point.x !== null && point.y !== null);
    if (!clean.length) return emptyState("Scatter gols × xG indisponível", "Esta edição não oferece xG no contrato de jogadores.");
    const width = 760, height = 430, pad = 48;
    const maxX = Math.max(...clean.map(point => point.x), 1);
    const maxY = Math.max(...clean.map(point => point.y), 1);
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Dispersão de gols por expected goals dos jogadores" });
    svg.append(svgNode("title", {}, "Cada ponto representa um jogador: xG no eixo horizontal e gols no vertical."));
    for (let tick = 0; tick <= 4; tick += 1) {
      const x = pad + (width - pad * 2) * tick / 4;
      const y = height - pad - (height - pad * 2) * tick / 4;
      svg.append(svgNode("line", { x1: x, y1: pad, x2: x, y2: height - pad, class: "chart-gridline" }));
      svg.append(svgNode("line", { x1: pad, y1: y, x2: width - pad, y2: y, class: "chart-gridline" }));
      svg.append(svgNode("text", { x, y: height - 17, class: "chart-axis", "text-anchor": "middle" }, formatValue(maxX * tick / 4)));
      svg.append(svgNode("text", { x: 34, y: y + 4, class: "chart-axis", "text-anchor": "end" }, formatValue(maxY * tick / 4)));
    }
    clean.forEach(point => {
      const tooltip = `Gols e xG · ${personName(point.item)} · ${teamName(point.item)} · ${formatValue(point.y)} gols · ${formatValue(point.x)} xG`;
      const circle = svgNode("circle", {
        cx: pad + point.x / maxX * (width - pad * 2),
        cy: height - pad - point.y / maxY * (height - pad * 2),
        r: Math.max(4, Math.min(10, 4 + (number(point.item?.shots) || 0) / 6)),
        class: "scatter-point",
        tabindex: "0",
        "aria-label": `${personName(point.item)}, ${formatValue(point.y)} gols, ${formatValue(point.x)} xG`,
      });
      svg.append(attachChartTooltip(circle, tooltip));
    });
    svg.append(svgNode("text", { x: width / 2, y: height - 2, class: "chart-axis-title", "text-anchor": "middle" }, "xG"));
    svg.append(svgNode("text", { x: 13, y: height / 2, class: "chart-axis-title", transform: `rotate(-90 13 ${height / 2})`, "text-anchor": "middle" }, "Gols"));
    return node("div", { class: "svg-chart" }, svg);
  }

  function svgNode(tag, attributes = {}, content = null) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    if (content !== null) element.textContent = text(content);
    return element;
  }

  function starPoints(cx, cy, outerRadius, innerRatio = 0.3) {
    return Array.from({ length: 10 }, (_, index) => {
      const angle = -Math.PI / 2 + index * Math.PI / 5;
      const radius = index % 2 === 0 ? outerRadius : outerRadius * innerRatio;
      return `${cx + Math.cos(angle) * radius},${cy + Math.sin(angle) * radius}`;
    }).join(" ");
  }

  let chartTooltipNode = null;

  function chartTooltip() {
    if (chartTooltipNode) return chartTooltipNode;
    chartTooltipNode = node("div", { class: "chart-tooltip", role: "tooltip" });
    document.body.append(chartTooltipNode);
    return chartTooltipNode;
  }

  function attachChartTooltip(element, content) {
    if (!content) return element;
    element.setAttribute("data-chart-tooltip", content);
    const show = event => {
      const tooltip = chartTooltip();
      tooltip.textContent = content;
      tooltip.classList.add("is-visible");
      const rect = element.getBoundingClientRect();
      const clientX = event?.clientX || rect.left + rect.width / 2;
      const clientY = event?.clientY || rect.top;
      const left = Math.min(window.innerWidth - tooltip.offsetWidth - 12, Math.max(12, clientX + 12));
      const top = Math.max(12, clientY - tooltip.offsetHeight - 12);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    };
    const hide = () => chartTooltipNode?.classList.remove("is-visible");
    element.addEventListener("pointerenter", show);
    element.addEventListener("pointermove", show);
    element.addEventListener("pointerleave", hide);
    element.addEventListener("focus", show);
    element.addEventListener("blur", hide);
    return element;
  }

  const SHOT_OUTCOME_LABELS = {
    goal: "Gol", save: "Defendido", saved: "Defendido", miss: "Para fora",
    off_target: "Para fora", block: "Bloqueado", blocked: "Bloqueado", post: "Na trave",
  };
  const BODY_PART_LABELS = {
    "right-foot": "Pé direito", "left-foot": "Pé esquerdo", head: "Cabeça", other: "Outra parte",
  };
  const SHOT_TYPE_LABELS = {
    assisted: "Jogada assistida", "open-play": "Bola rolando", corner: "Escanteio",
    "free-kick": "Falta", penalty: "Pênalti", rebound: "Rebote",
  };

  function shotKey(shot) {
    return String(first(shot, ["shot_id", "id"], [shot?.team_name, shot?.player_name, shot?.minute, shot?.x, shot?.y].join("|")));
  }

  function shotDetail(shot) {
    const team = shot?.team_name;
    const outcome = SHOT_OUTCOME_LABELS[String(shot?.shot_outcome || "").toLowerCase()] || "Finalização";
    const bodyPart = BODY_PART_LABELS[String(shot?.body_part || "").toLowerCase()] || "Não informado";
    const shotType = SHOT_TYPE_LABELS[String(shot?.shot_type || "").toLowerCase()] || "Não informado";
    return node("article", { class: "shot-detail" }, [
      node("div", { class: "shot-detail-head" }, [
        node("div", { class: "shot-detail-player" }, [
          flagNode(team),
          node("div", {}, [
            node("strong", { text: personName(shot) }),
            node("span", { text: displayTeamName(team) }),
          ]),
        ]),
        node("time", { text: `${formatValue(shot?.minute)}'` }),
      ]),
      node("dl", { class: "shot-detail-grid" }, [
        ["Resultado", outcome],
        ["xG", formatValue(Math.max(0, number(shot?.statsbomb_xg ?? shot?.xg) || 0))],
        ["Parte do corpo", bodyPart],
        ["Tipo de chance", shotType],
      ].map(([labelText, value]) => node("div", {}, [
        node("dt", { text: labelText }),
        node("dd", { text: value }),
      ]))),
    ]);
  }

  function shotMap(rows, { selectedKey = null, onSelect = null } = {}) {
    const home = first(rows[0] || {}, ["home_team"], null);
    const away = first(rows[0] || {}, ["away_team"], null);
    const shots = rows.map(item => {
      const rawX = number(item?.x);
      const rawY = number(item?.y);
      const isAway = away && item?.team_name === away;
      return {
        item,
        x: rawX === null ? null : isAway ? 120 - rawX : rawX,
        y: rawY === null ? null : rawY,
        teamIndex: isAway ? 1 : 0,
      };
    })
      .filter(shot => shot.x !== null && shot.y !== null);
    if (!shots.length) return emptyState("Mapa de chutes indisponível", "Não há coordenadas de finalização para esta edição.");
    const svg = svgNode("svg", {
      viewBox: "0 0 120 80",
      role: "img",
      "aria-label": `Campo com ${shots.length} finalizações`,
      style: matchPalette(home, away),
    });
    svg.append(svgNode("title", {}, "Mapa de finalizações. Gols aparecem em destaque."));
    const markings = [
      ["rect", { x: 1, y: 1, width: 118, height: 78 }],
      ["line", { x1: 60, y1: 1, x2: 60, y2: 79 }],
      ["circle", { cx: 60, cy: 40, r: 10 }],
      ["rect", { x: 1, y: 18, width: 18, height: 44 }],
      ["rect", { x: 101, y: 18, width: 18, height: 44 }],
      ["rect", { x: 1, y: 30, width: 6, height: 20 }],
      ["rect", { x: 113, y: 30, width: 6, height: 20 }],
      ["circle", { cx: 12, cy: 40, r: 0.7 }],
      ["circle", { cx: 108, cy: 40, r: 0.7 }],
    ];
    markings.forEach(([tag, attrs]) => svg.append(svgNode(tag, { ...attrs, class: "pitch-line" })));
    shots.forEach(({ item, x, y, teamIndex }) => {
      const goal = Boolean(item?.is_goal) || String(item?.shot_outcome).toLowerCase() === "goal";
      const cx = Math.max(1, Math.min(119, x));
      const cy = Math.max(1, Math.min(79, y));
      const size = Math.max(1.1, Math.min(3.8, 1.1 + (number(item?.statsbomb_xg) || 0) * 5));
      const key = shotKey(item);
      const selected = selectedKey === key;
      const marker = goal
        ? svgNode("polygon", {
          points: starPoints(cx, cy, size * 2, 0.28),
          class: `shot-point team-${teamIndex} is-goal${selected ? " is-selected" : ""}`,
          style: `--team-color:${teamColor(item?.team_name, teamIndex)}`,
          tabindex: "0",
          "aria-label": `${personName(item)}, ${teamName(item)}, gol, xG ${formatValue(item?.statsbomb_xg)}`,
          ...(onSelect ? { "aria-pressed": String(selected), role: "button" } : { role: "img" }),
        })
        : svgNode("circle", {
          cx,
          cy,
          r: size,
          class: `shot-point team-${teamIndex}${selected ? " is-selected" : ""}`,
          style: `--team-color:${teamColor(item?.team_name, teamIndex)}`,
          tabindex: "0",
          "aria-label": `${personName(item)}, ${teamName(item)}, finalização, xG ${formatValue(item?.statsbomb_xg)}`,
          ...(onSelect ? { "aria-pressed": String(selected), role: "button" } : { role: "img" }),
        });
      if (onSelect) {
        marker.addEventListener("click", () => onSelect(item));
        marker.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onSelect(item);
          }
        });
      }
      const tooltip = `${goal ? "Gol" : "Finalização"} · ${personName(item)} · ${teamName(item)} · xG ${formatValue(item?.statsbomb_xg)}`;
      svg.append(attachChartTooltip(marker, tooltip));
    });
    return node("div", { class: "pitch-wrap" }, [
      svg,
      node("div", { class: "chart-legend" }, [
        home ? node("span", {}, [node("i", { class: "legend-dot", style: `--team-color:${teamColor(home, 0)}` }), displayTeamName(home)]) : null,
        away ? node("span", {}, [node("i", { class: "legend-dot", style: `--team-color:${teamColor(away, 1)}` }), displayTeamName(away)]) : null,
        node("span", { class: "shot-symbol-legend", text: "Círculo = chute · Estrela = gol · Tamanho = xG · Cor = seleção" }),
      ]),
    ]);
  }

  function xgFlowPlot(rows) {
    const teams = [...new Set(rows.map(row => row.team_name).filter(Boolean))];
    const clean = rows
      .map(item => ({
        item,
        team: item.team_name,
        minute: number(item.minute),
        value: Math.max(0, number(item.cumulative_xg) || 0),
      }))
      .filter(point => point.team && point.minute !== null && point.value !== null)
      .sort((a, b) => a.minute - b.minute);
    if (!clean.length) {
      return emptyState("Fluxo de xG indisponível", "Selecione uma partida com finalizações e xG.");
    }
    const width = 760, height = 360, pad = 48;
    const maxMinute = Math.max(...clean.map(point => point.minute), 90);
    const maxValue = Math.max(...clean.map(point => point.value), 1);
    const svg = svgNode("svg", {
      viewBox: `0 0 ${width} ${height}`,
      role: "img",
      "aria-label": "Fluxo acumulado de expected goals por equipe",
    });
    svg.append(svgNode("title", {}, "Evolução acumulada do xG durante a partida."));
    for (let tick = 0; tick <= 4; tick += 1) {
      const x = pad + (width - pad * 2) * tick / 4;
      const y = height - pad - (height - pad * 2) * tick / 4;
      svg.append(svgNode("line", { x1: x, y1: pad, x2: x, y2: height - pad, class: "chart-gridline" }));
      svg.append(svgNode("line", { x1: pad, y1: y, x2: width - pad, y2: y, class: "chart-gridline" }));
      svg.append(svgNode("text", { x, y: height - 17, class: "chart-axis", "text-anchor": "middle" }, `${Math.round(maxMinute * tick / 4)}'`));
      svg.append(svgNode("text", { x: 36, y: y + 4, class: "chart-axis", "text-anchor": "end" }, formatValue(maxValue * tick / 4)));
    }
    teams.forEach((team, teamIndex) => {
      const points = clean.filter(point => point.team === team);
      if (!points.length) return;
      const color = teamColor(team, teamIndex);
      let path = `M ${pad} ${height - pad}`;
      points.forEach(point => {
        const x = pad + point.minute / maxMinute * (width - pad * 2);
        const y = height - pad - point.value / maxValue * (height - pad * 2);
        path += ` H ${x} V ${y}`;
      });
      const total = points.at(-1)?.value;
      const lineTooltip = `xG final · ${displayTeamName(team)}: ${formatValue(total)}`;
      const line = svgNode("path", {
        d: path,
        class: `xg-line team-${teamIndex % 2}`,
        style: `stroke:${color}`,
        fill: "none",
        tabindex: "0",
        "aria-label": lineTooltip,
      });
      svg.append(attachChartTooltip(line, lineTooltip));
      points.forEach(point => {
        if (point.item.is_terminal) return;
        const cx = pad + point.minute / maxMinute * (width - pad * 2);
        const cy = height - pad - point.value / maxValue * (height - pad * 2);
        const marker = point.item.is_goal
          ? svgNode("polygon", {
            points: starPoints(cx, cy, 8, 0.28),
            class: `xg-point team-${teamIndex % 2} is-goal`,
            style: `fill:${color}`,
            tabindex: "0",
            "aria-label": `Gol de ${displayTeamName(team)} aos ${formatValue(point.minute)} minutos`,
          })
          : svgNode("circle", {
            cx,
            cy,
            r: 3,
            class: `xg-point team-${teamIndex % 2}`,
            style: `fill:${color}`,
            tabindex: "0",
            "aria-label": `Finalização de ${displayTeamName(team)} aos ${formatValue(point.minute)} minutos`,
          });
        const player = point.item.player_name ? ` · ${point.item.player_name}` : "";
        const shotXg = number(point.item.xg ?? point.item.statsbomb_xg);
        const chance = shotXg !== null ? ` · chance de ${formatValue(shotXg)} xG` : "";
        const tooltip = `Fluxo de xG · ${displayTeamName(team)} · ${formatValue(point.minute)}'${player}${chance} · acumulado ${formatValue(point.value)} xG`;
        svg.append(attachChartTooltip(marker, tooltip));
      });
    });
    return node("div", { class: "svg-chart" }, [
      svg,
      node("div", { class: "chart-legend xg-total-legend" }, teams.map((team, index) => {
        const total = clean.filter(point => point.team === team).at(-1)?.value;
        return node("span", {}, [
          node("i", { class: `legend-line team-${index % 2}`, style: `--team-color:${teamColor(team, index)}` }),
          `${displayTeamName(team)} · ${formatValue(total)} xG`,
        ]);
      })),
    ]);
  }

  function mirroredComparison(rows, phase = false) {
    if (!rows.length) return emptyState("Comparação indisponível");
    const reserved = new Set(phase ? ["possession_state", "phase_name"] : ["metric", "unit", "section", "home_value", "away_value"]);
    const teams = [...new Set(rows.flatMap(row => Object.keys(row).filter(key => !reserved.has(key))))].slice(0, 2);
    if (teams.length < 2) return emptyState("Comparação indisponível", "São necessárias duas equipes no contrato.");
    return node("div", { class: "mirror-chart", style: matchPalette(teams[0], teams[1]) }, [
      node("div", { class: "mirror-head" }, [
        node("strong", { text: displayTeamName(teams[0]) }), node("span", { text: "Métrica" }), node("strong", { text: displayTeamName(teams[1]) }),
      ]),
      ...rows.slice(0, phase ? 18 : 14).map(row => {
        const left = number(row[teams[0]]) || 0;
        const right = number(row[teams[1]]) || 0;
        const max = Math.max(Math.abs(left), Math.abs(right), 1);
        const title = phase
          ? `${metricName(row.phase_name)} · ${metricName(row.possession_state)}`
          : metricName(row.metric);
        const tooltip = `${title} · ${displayTeamName(teams[0])}: ${formatValue(left)} · ${displayTeamName(teams[1])}: ${formatValue(right)}`;
        const comparison = node("div", { class: "mirror-row", tabIndex: 0, "aria-label": tooltip }, [
          node("div", { class: "mirror-side left" }, [
            node("strong", { text: formatValue(left) }),
            node("span", { style: `--bar-size:${Math.abs(left) / max * 100}%;background:var(--home-color)` }),
          ]),
          node("span", { class: "mirror-label", text: title }),
          node("div", { class: "mirror-side right" }, [
            node("span", { style: `--bar-size:${Math.abs(right) / max * 100}%;background:var(--away-color)` }),
            node("strong", { text: formatValue(right) }),
          ]),
        ]);
        return attachChartTooltip(comparison, tooltip);
      }),
    ]);
  }

  function flattenRow(row) {
    if (!isObject(row)) return { valor: row };
    const result = {};
    entries(row).forEach(([key, value]) => {
      if (technicalKeyPattern.test(key)) return;
      if (["string", "number", "boolean"].includes(typeof value) || value === null) result[key] = value;
    });
    return result;
  }

  function dataTable(rows) {
    const clean = rows.map(flattenRow).filter(row => entries(row).length);
    if (!clean.length) return null;
    const columns = [...new Set(clean.flatMap(row => Object.keys(row)))].slice(0, 9);
    return node("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": "Tabela de dados" }, [
      node("table", {}, [
        node("thead", {}, node("tr", {}, columns.map(column => node("th", { scope: "col", text: metricName(column) })))),
        node("tbody", {}, clean.slice(0, 100).map(row => node("tr", {}, columns.map(column => node("td", { text: formatValue(row[column]) }))))),
      ]),
    ]);
  }

  function dataDisclosure(title, rows) {
    return node("details", { class: "data-disclosure" }, [
      node("summary", {}, [
        node("span", { text: title }),
        node("strong", { text: `${rows.length} registros` }),
      ]),
      dataTable(rows),
    ]);
  }

  function objectCard(item, index) {
    const row = flattenRow(item);
    const titleKey = Object.keys(row).find(key => /name|team|player|match|group|title|winner|country/i.test(key)) || Object.keys(row)[0];
    const title = row[titleKey] ?? `Registro ${index + 1}`;
    const details = entries(row).filter(([key]) => key !== titleKey).slice(0, 6);
    return node("article", { class: "card" }, [
      node("span", { class: "card-kicker", text: `#${String(index + 1).padStart(2, "0")}` }),
      node("h3", { text: title }),
      node("dl", { class: "data-list" }, details.map(([key, value]) =>
        node("div", { class: "data-row" }, [node("dt", { text: label(key) }), node("dd", { text: formatValue(value) })])
      )),
    ]);
  }

  function emptyState(title = "Ainda não há dados para esta visão", detail = "Esta informação ainda não está disponível para o recorte selecionado.") {
    return node("section", { class: "state-card" }, [node("p", { class: "eyebrow", text: "Em breve" }), node("h2", { text: title }), node("p", { text: detail })]);
  }

  function dashboardShell(title, description, data) {
    const fragment = document.createDocumentFragment();
    fragment.append(pageHead(`Copa do Mundo · ${state.year}`, title, description));
    const message = first(data, ["notice", "message", "coverage_message", "warning"]);
    if (message && !technicalTextPattern.test(message)) fragment.append(node("aside", { class: "notice", text: message }));
    return fragment;
  }

  function renderArchiveOverview(data) {
    const fragment = dashboardShell("O torneio em perspectiva", "Resultados, protagonistas e contexto da edição em um só lugar.", data);
    const metrics = kpis(data.summary || {}, ["matches", "finished", "goals", "teams", "players", "shots", "xg", "champion", "goals_per_match"]);
    if (metrics) fragment.append(metrics);
    if (data.matches_today?.length) fragment.append(section("Jogos do dia", `${data.matches_today.length} partidas`, node("div", { class: "score-grid" }, data.matches_today.map(matchCard))));
    const scheduleColumns = [
      data.recent_matches?.length ? section("Últimos resultados", "Mais recentes", node("div", { class: "home-match-list" }, data.recent_matches.map(matchCard))) : null,
      data.upcoming_matches?.length ? section("Próximos jogos", "Agenda", node("div", { class: "home-match-list" }, data.upcoming_matches.map(matchCard))) : null,
    ].filter(Boolean);
    if (scheduleColumns.length) fragment.append(node("div", { class: "home-schedule-grid" }, scheduleColumns));

    const highlights = data.highlights || {};
    const featureCards = [
      ["Seleção em destaque", highlights.top_team, teamName],
      ["Jogador em destaque", highlights.top_player, personName],
    ].filter(([, item]) => item);
    if (featureCards.length) fragment.append(section("Destaques da edição", "Lideranças do recorte", node("div", { class: "feature-grid" },
      featureCards.map(([kicker, item, getName]) => node("article", { class: "feature-card" }, [
        node("p", { class: "eyebrow", text: kicker }),
        node("h3", { text: getName(item) }),
        node("dl", { class: "feature-stats" }, entries(item)
          .filter(([key, value]) => number(value) !== null && !/edition|year/i.test(key))
          .slice(0, 4)
          .map(([key, value]) => node("div", {}, [node("dt", { text: metricName(key) }), node("dd", { text: formatValue(value) })]))),
      ]))
    )));
    if (!metrics && !featureCards.length) fragment.append(emptyState());
    els.view.replaceChildren(fragment);
  }

  function renderOverview(data) {
    if (state.year !== DEFAULT_YEAR) {
      renderArchiveOverview(data);
      return;
    }
    state.overviewData = data;
    const fragment = dashboardShell(
      state.year === DEFAULT_YEAR ? "Copa do Mundo 2026" : "O torneio em perspectiva",
      "Agenda, resultados e protagonistas da edição em um só lugar.",
      data
    );
    const summary = homeSummaryStrip(data.summary || {});
    if (summary) fragment.append(summary);

    const pulse = homePulse(data.pulse || {});
    if (pulse) fragment.append(section("Pulso da Copa", data.pulse?.current_phase || "Agora no torneio", pulse, "home-pulse-section"));

    const bracket = homeBracketSummary(data.knockout_summary || {});
    if (bracket) fragment.append(section("Caminho do mata-mata", "Rota até a final", bracket, "home-bracket-section"));

    const leaders = data.leaders || {};
    const leaderPanels = [
      ["Jogadores", "Gols", leaders.players?.goals, "goals", "player"],
      ["Jogadores", "xG", leaders.players?.xg, "xg", "player"],
      ["Jogadores", "Assistências", leaders.players?.assists, "assists", "player"],
      ["Jogadores", "Finalizações", leaders.players?.shots, "shots", "player"],
      ["Seleções", "Maior xG", leaders.teams?.xg, "xg", "team"],
      ["Seleções", "Saldo de xG", leaders.teams?.xg_difference, "xg_difference", "team"],
      ["Seleções", "Gols marcados", leaders.teams?.goals_for, "goals_for", "team"],
      ["Partidas", "Mais finalizações", leaders.matches?.shots, "shots", "match"],
      ["Partidas", "Maior xG total", leaders.matches?.xg_total, "xg_total", "match"],
    ].filter(([, , rows]) => rows?.length).map(([kicker, title, rows, metric, entity]) =>
      homeRankingPanel({ kicker, title, rows, metric, entity })
    );
    if (leaderPanels.length) fragment.append(section("Líderes da Copa", "Clique para ampliar", node("div", { class: "home-ranking-grid" }, leaderPanels)));

    const explorer = homeDiscoveryLab(data.discoveries || {});
    if (explorer) fragment.append(section("Explorar estatísticas", "Leituras menos óbvias da edição", explorer));
    if (!summary && !leaderPanels.length) fragment.append(emptyState());
    els.view.replaceChildren(fragment);
  }

  function homeSummaryStrip(summary) {
    const groups = [
      ["Essencial", [
        ["Partidas", summary.matches], ["Encerrados", summary.finished],
        ["Gols", summary.goals], ["Gols por jogo", summary.goals_per_match],
      ]],
      ["Análise", [
        ["Finalizações", summary.shots], ["xG total", summary.xg],
        ["Jogadores", summary.players], ["Seleções", summary.teams],
      ]],
    ].map(([labelText, metrics]) => [labelText, metrics.filter(([, value]) => value !== null && value !== undefined)]).filter(([, metrics]) => metrics.length);
    if (!groups.length) return null;
    return section("Resumo da edição", "Panorama rápido", node("div", { class: "home-summary-strip" }, groups.map(([labelText, metrics]) =>
      node("div", { class: "home-summary-group" }, [
        node("span", { class: "home-summary-group-label", text: labelText }),
        ...metrics.map(([metric, value]) => node("div", { class: "home-summary-metric" }, [
          node("strong", { text: formatValue(value) }),
          node("span", { text: metric }),
        ])),
      ])
    )), "home-summary-section");
  }

  function knockoutSideNode(side, className = "") {
    if (side?.defined && side?.team_name) return teamLabel(side.team_name, `home-bracket-team ${className}`.trim());
    return node("span", { class: `home-bracket-team is-placeholder ${className}`.trim(), text: side?.placeholder || "A definir" });
  }

  function homeBracketMatch(match, phase = null) {
    const canOpen = Boolean(match?.match_id);
    const hasScore = match?.home_score !== null && match?.home_score !== undefined
      && match?.away_score !== null && match?.away_score !== undefined;
    const date = match?.kickoff_at || match?.match_date;
    const center = hasScore
      ? `${formatValue(match.home_score)}–${formatValue(match.away_score)}`
      : date ? new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(date)) : "A definir";
    return node("button", {
      type: "button",
      class: "home-bracket-match",
      disabled: !canOpen,
      onclick: canOpen ? () => openMatchQuickView({ ...match, stage: phase || match.stage }) : null,
    }, [
      knockoutSideNode(match?.home, "home"),
      node("strong", { class: "home-bracket-center", text: center }),
      knockoutSideNode(match?.away, "away"),
    ]);
  }

  function homePulse(pulse) {
    const today = pulse?.today_matches || [];
    const classified = pulse?.classified_recent || [];
    const next = pulse?.next_matchups || [];
    if (!pulse?.current_phase && !today.length && !classified.length && !next.length) return null;
    const columns = [
      node("article", { class: "home-pulse-column" }, [
        node("header", {}, [node("small", { text: "Agora" }), node("h3", { text: "Agenda de hoje" })]),
        today.length
          ? node("div", { class: "home-pulse-list" }, today.slice(0, 4).map((match, index) => compactMatchRow(match, { featured: index === 0 })))
          : node("p", { class: "home-empty-line", text: "Não há jogos programados para hoje." }),
      ]),
      node("article", { class: "home-pulse-column" }, [
        node("header", {}, [node("small", { text: "Consequências" }), node("h3", { text: "Quem avançou" })]),
        classified.length
          ? node("div", { class: "home-pulse-list" }, classified.map(item => node("button", {
            type: "button", class: "home-pulse-story", onclick: () => openMatchQuickView(item.match),
          }, [
            flagNode(item.winner_name),
            node("span", {}, [
              node("strong", { text: displayTeamName(item.winner_name) }),
              node("small", { text: translateTeamsInText(item.narrative) }),
            ]),
          ])))
          : node("p", { class: "home-empty-line", text: "As próximas classificações aparecerão aqui." }),
      ]),
      node("article", { class: "home-pulse-column" }, [
        node("header", {}, [node("small", { text: pulse?.next_phase || "Próxima fase" }), node("h3", { text: "Próximos encaixes" })]),
        next.length
          ? node("div", { class: "home-pulse-list" }, next.map(match => homeBracketMatch(match)))
          : node("p", { class: "home-empty-line", text: "Os próximos confrontos ainda estão sendo definidos." }),
      ]),
    ];
    return node("div", { class: "home-pulse" }, [
      node("div", { class: "home-pulse-phase" }, [
        node("small", { text: "Fase atual" }),
        node("strong", { text: pulse.current_phase || "Em andamento" }),
      ]),
      node("div", { class: "home-pulse-grid" }, columns),
    ]);
  }

  function homeBracketSummary(summary) {
    const rounds = summary?.rounds || [];
    if (!rounds.length) return null;
    return node("div", { class: "home-bracket-summary" }, [
      node("div", { class: "home-bracket-rounds" }, rounds.map(round => node("article", { class: "home-bracket-round" }, [
        node("header", {}, [node("small", { text: round.name === summary.current_phase ? "Fase atual" : "Na sequência" }), node("h3", { text: round.name })]),
        node("div", { class: "home-bracket-matches" }, (round.matches || []).slice(0, 4).map(match => homeBracketMatch(match, round.id))),
      ]))),
      node("button", { type: "button", class: "home-bracket-cta", onclick: () => goTo(state.year, "competition") }, [
        node("span", { text: "Ver chave completa" }), node("span", { "aria-hidden": "true", text: "→" }),
      ]),
    ]);
  }

  function homeMatchStatus(match) {
    const status = String(match?.status || "").toLowerCase();
    if (status === "finished") return "Encerrado";
    if (homeMatchIsLive(match)) return "Ao vivo";
    const date = new Date(match?.match_date || match?.kickoff_at || "");
    const hasScore = match?.home_score !== null && match?.home_score !== undefined && match?.away_score !== null && match?.away_score !== undefined;
    if (!Number.isNaN(date.getTime()) && hasScore && Date.now() - date.getTime() > 4 * 60 * 60 * 1000) return "Encerrado";
    if (!Number.isNaN(date.getTime()) && date.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" }) === new Date().toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" })) return "Hoje";
    return "Em breve";
  }

  function homeMatchIsLive(match) {
    const status = String(match?.status || "").toLowerCase();
    if (!/live|in_progress/.test(status)) return false;
    const kickoff = new Date(match?.match_date || match?.kickoff_at || "").getTime();
    if (Number.isNaN(kickoff)) return false;
    const elapsed = Date.now() - kickoff;
    return elapsed >= -15 * 60 * 1000 && elapsed <= 4 * 60 * 60 * 1000;
  }

  function homeMatchCenter(match) {
    const status = String(match?.status || "").toLowerCase();
    const hasScore = match?.home_score !== null && match?.home_score !== undefined && match?.away_score !== null && match?.away_score !== undefined;
    const date = new Date(match?.match_date || match?.kickoff_at || "");
    if (hasScore && (status === "finished" || homeMatchIsLive(match) || Date.now() - date.getTime() > 4 * 60 * 60 * 1000)) return `${formatValue(match.home_score)}–${formatValue(match.away_score)}`;
    if (Number.isNaN(date.getTime())) return "×";
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit" }).format(date);
  }

  function homeStageLabel(match) {
    if (match?.group_name) return `Grupo ${match.group_name}`;
    const stage = String(match?.stage || "").toLowerCase();
    const labels = {
      group_stage: "Fase de grupos", round_of_32: "16 avos",
      round_of_16: "Oitavas de final", quarter_final: "Quartas de final",
      semi_final: "Semifinal", semifinal: "Semifinal",
      third_place: "Disputa de 3º lugar", final: "Final",
    };
    return labels[stage] || "Copa do Mundo 2026";
  }

  function compactMatchRow(match, { featured = false } = {}) {
    const home = match?.home_team;
    const away = match?.away_team;
    const context = homeStageLabel(match);
    return node("button", {
      type: "button",
      class: `home-match-row${featured ? " is-featured" : ""}`,
      style: matchPalette(home, away),
      onclick: () => openMatchQuickView(match),
      "aria-label": `${displayTeamName(home)} contra ${displayTeamName(away)}. ${homeMatchStatus(match)}.`,
    }, [
      node("span", { class: "home-match-meta" }, [
        node("b", { text: homeMatchStatus(match) }),
        node("time", { dateTime: match?.match_date || "", text: formatMatchDate(match?.match_date) }),
      ]),
      node("span", { class: "home-match-scoreline" }, [
        teamLabel(home, "home-match-team home"),
        node("strong", { class: "home-match-score", text: homeMatchCenter(match) }),
        teamLabel(away, "home-match-team away"),
      ]),
      node("span", { class: "home-match-context", text: context }),
    ]);
  }

  function homeRankingEntity(item, entity) {
    if (entity === "match") return node("span", { class: "home-ranking-match" }, [
      teamLabel(item.home_team), node("i", { text: "×" }), teamLabel(item.away_team),
    ]);
    const team = item?.team_name;
    return node("span", { class: "home-ranking-entity" }, [
      flagNode(team), node("span", { text: entity === "player" ? personName(item) : teamName(item) }),
    ]);
  }

  function homeRankingValue(item, metric) {
    if (item?.display_value) return item.display_value;
    const parsed = number(item?.[metric]);
    const value = metric === "xg_difference" && parsed !== null
      ? (parsed > 0 ? `+${formatValue(parsed)}` : formatValue(parsed))
      : formatValue(item?.[metric]);
    if (metric === "goals") return `${value} gols`;
    if (metric === "assists") return `${value} assist.`;
    if (metric === "shots") return `${value} chutes`;
    return value;
  }

  function homeRankingValueClass(item, metric) {
    if (metric !== "xg_difference") return "";
    const value = number(item?.[metric]);
    if (value === null || value === 0) return "is-neutral";
    return value > 0 ? "is-positive" : "is-negative";
  }

  function openHomeEntityQuickView(item, entity) {
    if (entity === "player") openPlayerQuickView(item);
    else if (entity === "team") openHomeTeamQuickView(item);
    else openMatchQuickView(item);
  }

  function homeRankingRow(item, index, metric, entity) {
    return node("button", { type: "button", class: "home-ranking-row", onclick: () => openHomeEntityQuickView(item, entity) }, [
      node("span", { class: "home-rank", text: String(index + 1) }),
      homeRankingEntity(item, entity),
      node("strong", { class: `home-ranking-value ${homeRankingValueClass(item, metric)}`.trim(), text: homeRankingValue(item, metric) }),
    ]);
  }

  function homeRankingPanel({ kicker, title, rows, metric, entity }) {
    return node("article", { class: "home-ranking-panel" }, [
      node("button", { type: "button", class: "home-ranking-open", onclick: () => openRankingQuickView({ kicker, title, rows, metric, entity }) }, [
        node("span", {}, [node("small", { text: kicker }), node("strong", { text: title })]),
        node("span", { class: "home-ranking-expand", text: `Ver ranking (${rows.length})` }),
      ]),
      node("div", { class: "home-ranking-list" }, rows.slice(0, 5).map((item, index) => homeRankingRow(item, index, metric, entity))),
    ]);
  }

  function openPlayerQuickView(player) {
    openQuickView({
      kicker: "Resumo do jogador",
      titleContent: node("span", { class: "quick-entity-title" }, [flagNode(player.team_name, "flag-medium"), node("span", { text: personName(player) })]),
      rows: [
        ["Seleção", teamName(player)], ["Posição", positionLabel(player.position)],
        ["Jogos", player.games], ["Minutos", player.minutes_played],
        ["Gols", player.goals], ["Assistências", player.assists],
        ["xG", player.xg], ["Rating", player.rating],
      ],
      actionLabel: player.player_id ? "Abrir jogador" : null,
      onAction: player.player_id ? () => routeTo("players", player.player_id) : null,
    });
  }

  function openHomeTeamQuickView(team) {
    const selectedTeam = rawTeamName(team);
    const nextMatches = [
      ...(state.overviewData?.matches_today || []),
      ...(state.overviewData?.upcoming_matches || []),
    ].filter((match, index, rows) =>
      [match.home_team, match.away_team].includes(selectedTeam)
      && rows.findIndex(item => item.match_id === match.match_id) === index
    ).slice(0, 3);
    const extra = node("section", { class: "quick-view-extra" }, [
      node("h3", { text: "Próximos jogos" }),
      nextMatches.length
        ? node("div", { class: "quick-view-match-list" }, nextMatches.map(match => compactMatchRow(match)))
        : node("p", { text: "O próximo compromisso ainda não está definido no calendário." }),
    ]);
    openQuickView({
      kicker: "Resumo da seleção",
      titleContent: teamLabel(rawTeamName(team), "quick-entity-title"),
      rows: [
        ["Grupo", team.group_name ? `Grupo ${team.group_name}` : null], ["Jogos", team.played],
        ["Pontos", team.points], ["Gols", team.goals_for !== undefined ? `${team.goals_for} pró · ${team.goals_against} contra` : null],
        ["Saldo", team.goal_difference !== undefined ? signedStandingValue(team.goal_difference) : null],
        ["xG", team.xg], ["Saldo de xG", team.xg_difference],
      ],
      extra,
      actionLabel: team.team_id ? "Abrir seleção" : null,
      onAction: team.team_id ? () => routeTo("teams", team.team_id) : null,
    });
  }

  function openRankingQuickView({ kicker, title, rows, metric, entity }) {
    const entityLabel = entity === "match" ? "Partida" : entity === "team" ? "Seleção" : "Jogador";
    const extra = node("section", { class: "ranking-detail" }, [
      node("div", { class: "ranking-detail-head" }, [
        node("span", { text: "Pos." }),
        node("span", { class: "ranking-detail-column", text: entityLabel }),
        node("span", { text: title }),
      ]),
      node("div", { class: "ranking-detail-list" }, rows.map((item, index) => homeRankingRow(item, index, metric, entity))),
    ]);
    openQuickView({
      kicker: `Ranking · ${kicker}`,
      titleContent: title,
      rows: [["Ranking", `${rows.length} posições disponíveis`]],
      extra,
      layout: "modal",
      actionLabel: null,
      onAction: null,
    });
  }

  function discoveryValue(metric, row) {
    const value = number(row?.value);
    if (value === null) return "—";
    if (metric.unit === "%") return `${formatValue(value)}%`;
    if (metric.unit === "min") return `${formatValue(value)}'`;
    if (metric.unit === "gols") return `${formatValue(value)} gols/100 min`;
    if (metric.unit === "xG") return `${formatValue(value)} xG`;
    return `${formatValue(value)} ${metric.unit || ""}`.trim();
  }

  function openDiscoveryQuickView(metric) {
    const rows = (metric.rows || []).map(row => ({ ...row, display_value: discoveryValue(metric, row) }));
    const extra = node("section", { class: "ranking-detail discovery-ranking-detail" }, [
      node("p", { class: "discovery-modal-description", text: metric.description }),
      node("p", { class: "discovery-modal-rule", text: metric.eligibility }),
      node("div", { class: "ranking-detail-head" }, [
        node("span", { text: "Pos." }),
        node("span", { class: "ranking-detail-column", text: metric.entity === "match" ? "Partida" : metric.entity === "team" ? "Seleção" : "Jogador" }),
        node("span", { text: "Valor" }),
      ]),
      node("div", { class: "ranking-detail-list" }, rows.map((item, index) => homeRankingRow(item, index, "value", metric.entity))),
    ]);
    openQuickView({
      kicker: "Explorar estatísticas",
      titleContent: metric.title,
      rows: [],
      extra,
      layout: "modal",
      actionLabel: null,
      onAction: null,
    });
  }

  function homeDiscoveryLab(discoveries) {
    const categories = [
      ["players", "Jogadores", "Eficiência e influência individual", "Gols por tempo em campo, qualidade das chances e conversão."],
      ["teams", "Seleções", "Perfis coletivos da competição", "Produção ofensiva, resistência defensiva e aproveitamento."],
      ["matches", "Partidas", "Jogos fora da curva", "Equilíbrio, intensidade e volume de ações em cada confronto."],
      ["curiosities", "Curiosidades", "Recortes especiais da edição", "Momentos e marcas que ajudam a contar a história da Copa."],
    ].map(([key, labelText, kicker, description]) => ({
      key, label: labelText, kicker, description,
      metrics: (discoveries?.[key] || []).filter(metric => metric.rows?.length),
    })).filter(category => category.metrics.length);
    if (!categories.length) return null;
    return node("div", { class: "home-discovery-lab" }, [
      node("div", { class: "discovery-category-grid" }, categories.map(homeDiscoveryCategoryCard)),
    ]);
  }

  function homeDiscoveryCategoryCard(category) {
    return node("button", {
      type: "button",
      class: "discovery-category-card",
      onclick: () => openDiscoveryCategoryView(category),
      "aria-label": `Explorar estatísticas de ${category.label.toLowerCase()}`,
    }, [
      node("span", { class: "discovery-category-head" }, [
        node("span", {}, [node("small", { text: category.kicker }), node("strong", { text: category.label })]),
        node("span", { class: "discovery-category-arrow", "aria-hidden": "true", text: "→" }),
      ]),
      node("span", { class: "discovery-category-description", text: category.description }),
      node("span", { class: "discovery-category-preview" }, category.metrics.slice(0, 3).map(metric => {
        const leader = metric.rows[0];
        return node("span", { class: "discovery-preview-row" }, [
          node("span", {}, [node("small", { text: metric.title }), homeRankingEntity(leader, metric.entity)]),
          node("b", { text: discoveryValue(metric, leader) }),
        ]);
      })),
      node("span", { class: "discovery-category-action", text: `Explorar ${category.label.toLowerCase()}` }),
    ]);
  }

  function openDiscoveryCategoryView(category) {
    const extra = node("section", { class: "discovery-category-detail" }, [
      node("p", { class: "discovery-category-intro", text: category.description }),
      node("div", { class: "discovery-category-rankings" }, category.metrics.map(homeDiscoveryMetricPanel)),
    ]);
    openQuickView({
      kicker: "Explorar estatísticas",
      titleContent: `Explorar ${category.label.toLowerCase()}`,
      rows: [],
      extra,
      layout: "modal",
      actionLabel: null,
      onAction: null,
    });
  }

  function homeDiscoveryMetricPanel(metric) {
    const rows = metric.rows.map(row => ({ ...row, display_value: discoveryValue(metric, row) }));
    return node("article", { class: "discovery-metric-panel" }, [
      node("header", {}, [
        node("span", {}, [node("h3", { text: metric.title }), node("p", { text: metric.description })]),
        node("small", { text: metric.eligibility }),
      ]),
      node("div", { class: "home-ranking-list" }, rows.slice(0, 5).map((item, index) => homeRankingRow(item, index, "value", metric.entity))),
      node("button", { type: "button", class: "discovery-ranking-open", onclick: () => openDiscoveryQuickView(metric), text: "Ver ranking completo" }),
    ]);
  }

  function homeHighlights(highlights, leaders) {
    const team = highlights.top_team;
    const player = highlights.top_player;
    const match = leaders.matches?.shots?.[0];
    const items = [
      team ? { kicker: "Seleção em destaque", entity: "team", item: team, reason: `${formatValue(team.xg)} xG e saldo de ${signedStandingValue(team.goal_difference)} gols na fase de grupos.`, stats: [["Pts", team.points], ["GP", team.goals_for], ["GC", team.goals_against]] } : null,
      player ? { kicker: "Jogador em destaque", entity: "player", item: player, reason: `${formatValue(player.goals)} gols em ${formatValue(player.minutes_played)} minutos, liderando a artilharia.`, stats: [["Jogos", player.games], ["Gols", player.goals], ["Assist.", player.assists]] } : null,
      match ? { kicker: "Partida em destaque", entity: "match", item: match, reason: `${formatValue(match.shots)} finalizações fizeram deste o jogo de maior volume ofensivo.`, stats: [["Chutes", match.shots], ["xG", match.xg_total]] } : null,
    ].filter(Boolean);
    if (!items.length) return null;
    return node("div", { class: "home-highlight-grid" }, items.map(({ kicker, entity, item, reason, stats }) =>
      node("button", { type: "button", class: "home-highlight-card", onclick: () => openHomeEntityQuickView(item, entity) }, [
        node("span", { class: "eyebrow", text: kicker }),
        node("strong", { class: "home-highlight-name" }, homeRankingEntity(item, entity)),
        node("span", { class: "home-highlight-reason", text: reason }),
        node("span", { class: "home-highlight-stats" }, stats.filter(([, value]) => value !== null && value !== undefined).map(([labelText, value]) => node("span", {}, [node("small", { text: labelText }), node("b", { text: formatValue(value) })]))),
      ])
    ));
  }

  function renderTeams(data) {
    const fragment = dashboardShell("Países em foco", "Tabela, produção coletiva e perfis das seleções no recorte atual.", data);
    const metrics = kpis(data.summary || {}, ["teams", "goals", "shots", "xg"]);
    if (metrics) fragment.append(metrics);
    if (data.items?.length) {
      fragment.append(section("Todos os países", `${data.items.length} seleções`,
        node("div", { class: "card-grid" }, data.items.map(team => entityCard(team, {
          page: "teams",
          idKey: "team_id",
          title: teamName,
          kicker: team.group_name || "Seleção",
          metrics: ["points", "played", "goals_for", "goals_against", "xg", "shots"],
        })))
      ));
    }
    const panels = rankingPanels(data.rankings || {}, { entity: "team", maxPanels: 6 });
    if (panels) fragment.append(section("Rankings por seleção", `${entries(data.rankings).length} métricas disponíveis`, panels));
    if (!metrics && !panels) fragment.append(emptyState());
    els.view.replaceChildren(fragment);
  }

  function renderPlayers(data) {
    const fragment = dashboardShell("Jogadores da Copa", "Compare produção, eficiência e perfil de atuação em toda a edição.", data);
    const experience = playerAnalysisExperience(data);
    if (experience) fragment.append(experience);
    else fragment.append(emptyState("Jogadores indisponíveis", "As estatísticas individuais ainda não estão disponíveis."));
    els.view.replaceChildren(fragment);
  }

  function playerAnalysisExperience(data) {
    const players = (data.items || []).filter(player => player.player_id && number(player.minutes_played) > 0);
    if (!players.length) return null;
    const filters = { search: "", position: "all", team: "all", minMinutes: 0, minShots: 0 };
    let selectedId = null;
    let selectedData = null;
    let scopeValue = "all";
    let activeTab = "general";
    let requestToken = 0;

    const scatterHost = node("div", { class: "players-scatter-host" });
    const tableHost = node("div", { class: "players-table-host" });
    const profileHost = node("div", { class: "player-profile-host" });
    const resultMeta = node("span");
    const selectedCopy = node("span", { text: "Nenhum jogador selecionado" });
    const clearButton = node("button", { type: "button", class: "players-clear-selection", text: "Limpar seleção", disabled: true });
    const contextSelect = node("select", { disabled: true });
    const tabButtons = [
      ["general", "Geral"], ["radar", "Radar"], ["shots", "Finalizações"], ["distribution", "Distribuição"],
    ].map(([key, labelText]) => node("button", {
      type: "button", text: labelText, "data-tab": key, disabled: true,
      onclick: () => { activeTab = key; drawTabs(); drawProfile(); },
    }));

    const searchInput = node("input", { type: "search", placeholder: "Nome do jogador", autocomplete: "off" });
    const positionSelect = playerFilterSelect("Posição", [
      ["all", "Todas"], ...(data.filters?.positions || []).map(value => [value, positionLabel(value)]),
    ]);
    const teamSelect = playerFilterSelect("Seleção", [
      ["all", "Todas"], ...(data.filters?.teams || []).map(value => [value, displayTeamName(value)]),
    ]);
    const minutesInput = node("input", { type: "number", min: 0, step: 30, value: 0, inputMode: "numeric" });
    const shotsInput = node("input", { type: "number", min: 0, step: 1, value: 0, inputMode: "numeric" });

    const controls = node("section", { class: "players-control-panel", "aria-label": "Controles da análise de jogadores" }, [
      node("div", { class: "players-selection-control" }, [
        node("label", {}, [node("span", { text: "Buscar jogador" }), searchInput]),
        node("div", { class: "players-selected-context" }, [
          node("span", { class: "players-selected-copy" }, [node("small", { text: "Em análise" }), selectedCopy]),
          clearButton,
        ]),
      ]),
      node("div", { class: "players-filter-grid" }, [
        positionSelect.label,
        teamSelect.label,
        node("label", {}, [node("span", { text: "Minutos mínimos" }), minutesInput]),
        node("label", {}, [node("span", { text: "Finalizações mínimas" }), shotsInput]),
        node("label", { class: "players-context-select" }, [node("span", { text: "Recorte da análise" }), contextSelect]),
      ]),
      node("div", { class: "player-profile-tabs", role: "tablist", "aria-label": "Visualização do jogador" }, tabButtons),
    ]);

    const overview = section("Visão geral dos jogadores", "", node("div", { class: "players-analysis-layout" }, [
      node("article", { class: "players-scatter-panel" }, [
        node("div", { class: "players-panel-head" }, [
          node("span", {}, [node("h3", { text: "Gols × xG" }), node("p", { text: "Clique em um ponto para abrir o perfil do jogador." })]),
          resultMeta,
        ]),
        scatterHost,
      ]),
      node("article", { class: "players-list-panel" }, [
        node("div", { class: "players-panel-head" }, [node("span", {}, [node("h3", { text: "Lista de jogadores" }), node("p", { text: "Selecione uma linha para analisar." })])]),
        tableHost,
      ]),
    ]), "players-overview-section");
    const profileSection = section("Perfil do jogador", "Análise agregada por recorte", profileHost, "player-inline-profile");

    function playerFilterSelect(labelText, options) {
      const select = node("select", {}, options.map(([value, optionLabel]) => node("option", { value, text: optionLabel })));
      return { select, label: node("label", {}, [node("span", { text: labelText }), select]) };
    }

    function filteredPlayers() {
      const query = filters.search.trim().toLocaleLowerCase("pt-BR");
      return players.filter(player => {
        const haystack = `${personName(player)} ${displayTeamName(player.team_name)}`.toLocaleLowerCase("pt-BR");
        return (!query || haystack.includes(query))
          && (filters.position === "all" || player.position === filters.position)
          && (filters.team === "all" || player.team_name === filters.team)
          && (number(player.minutes_played) || 0) >= filters.minMinutes
          && (number(player.shots) || 0) >= filters.minShots;
      });
    }

    function drawOverview() {
      const rows = filteredPlayers();
      resultMeta.textContent = `${rows.length} jogadores`;
      scatterHost.replaceChildren(playerScatterPlot(rows, { selectedId, onSelect: selectPlayer }));
      tableHost.replaceChildren(playerOverviewTable(rows, { selectedId, onSelect: selectPlayer }));
    }

    function drawTabs() {
      tabButtons.forEach(button => {
        const active = button.dataset.tab === activeTab;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", String(active));
      });
    }

    function drawContextOptions() {
      const options = [
        node("option", { value: "all", text: "Edição inteira" }),
        node("option", { value: "group_stage", text: "Fase de grupos" }),
        node("option", { value: "knockout", text: "Mata-mata" }),
      ];
      (selectedData?.available_matches || []).forEach(match => options.push(
        node("option", { value: `match:${match.match_id}`, text: `Jogo: ${translateTeamsInText(match.label)}` })
      ));
      contextSelect.replaceChildren(...options);
      contextSelect.value = scopeValue;
    }

    function drawProfile() {
      if (!selectedId) {
        profileHost.replaceChildren(node("p", { class: "players-profile-empty", text: "Clique em um jogador no scatter ou na tabela para abrir radar, finalizações e distribuições." }));
        return;
      }
      if (!selectedData) {
        profileHost.replaceChildren(node("p", { class: "players-profile-loading", text: "Carregando perfil do jogador..." }));
        return;
      }
      profileHost.replaceChildren(playerProfileView(selectedData, activeTab));
    }

    async function loadSelectedPlayer() {
      const token = ++requestToken;
      selectedData = null;
      drawProfile();
      const [scope, matchId] = scopeValue.startsWith("match:") ? ["match", scopeValue.slice(6)] : [scopeValue, null];
      const params = new URLSearchParams({ scope });
      if (matchId) params.set("match_id", matchId);
      try {
        const payload = await getJSON(`/editions/${encodeURIComponent(state.year)}/players/${encodeURIComponent(selectedId)}?${params}`);
        if (token !== requestToken) return;
        selectedData = payload;
        drawContextOptions();
        drawProfile();
      } catch (error) {
        if (token !== requestToken || error?.name === "AbortError") return;
        profileHost.replaceChildren(emptyState("Perfil indisponível", "Não foi possível carregar este recorte do jogador."));
      }
    }

    function selectPlayer(player) {
      selectedId = player.player_id;
      selectedData = null;
      scopeValue = "all";
      activeTab = "general";
      selectedCopy.replaceChildren(flagNode(player.team_name), node("strong", { text: personName(player) }), node("span", { text: positionLabel(player.position) }));
      clearButton.disabled = false;
      contextSelect.disabled = false;
      tabButtons.forEach(button => { button.disabled = false; });
      drawTabs();
      drawContextOptions();
      drawOverview();
      loadSelectedPlayer();
      profileSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function clearSelection() {
      requestToken += 1;
      selectedId = null;
      selectedData = null;
      scopeValue = "all";
      selectedCopy.textContent = "Nenhum jogador selecionado";
      clearButton.disabled = true;
      contextSelect.disabled = true;
      tabButtons.forEach(button => { button.disabled = true; });
      drawTabs();
      drawOverview();
      drawProfile();
    }

    searchInput.oninput = event => { filters.search = event.target.value; drawOverview(); };
    positionSelect.select.onchange = event => { filters.position = event.target.value; drawOverview(); };
    teamSelect.select.onchange = event => { filters.team = event.target.value; drawOverview(); };
    minutesInput.oninput = event => { filters.minMinutes = Math.max(0, number(event.target.value) || 0); drawOverview(); };
    shotsInput.oninput = event => { filters.minShots = Math.max(0, number(event.target.value) || 0); drawOverview(); };
    contextSelect.onchange = event => { scopeValue = event.target.value; loadSelectedPlayer(); };
    clearButton.onclick = clearSelection;

    drawContextOptions();
    drawTabs();
    drawOverview();
    drawProfile();
    return node("div", { class: "players-experience" }, [controls, overview, profileSection]);
  }

  function playerScatterPlot(rows, { selectedId = null, onSelect = null } = {}) {
    const clean = rows.map(item => ({ item, x: number(item.xg), y: number(item.goals) })).filter(point => point.x !== null && point.y !== null);
    if (!clean.length) return emptyState("Scatter indisponível", "Ajuste os filtros para encontrar jogadores com gols e xG.");
    const width = 760, height = 430, pad = 48;
    const maxX = Math.max(...clean.map(point => point.x), 1);
    const maxY = Math.max(...clean.map(point => point.y), 1);
    const xAt = value => pad + value / maxX * (width - pad * 2);
    const yAt = value => height - pad - value / maxY * (height - pad * 2);
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Dispersão de gols por xG dos jogadores" });
    for (let tick = 0; tick <= 4; tick += 1) {
      const x = pad + (width - pad * 2) * tick / 4;
      const y = height - pad - (height - pad * 2) * tick / 4;
      svg.append(svgNode("line", { x1: x, y1: pad, x2: x, y2: height - pad, class: "chart-gridline" }));
      svg.append(svgNode("line", { x1: pad, y1: y, x2: width - pad, y2: y, class: "chart-gridline" }));
      svg.append(svgNode("text", { x, y: height - 17, class: "chart-axis", "text-anchor": "middle" }, formatValue(maxX * tick / 4)));
      svg.append(svgNode("text", { x: 34, y: y + 4, class: "chart-axis", "text-anchor": "end" }, formatValue(maxY * tick / 4)));
    }
    const referenceMax = Math.min(maxX, maxY);
    svg.append(svgNode("line", { x1: xAt(0), y1: yAt(0), x2: xAt(referenceMax), y2: yAt(referenceMax), class: "scatter-reference-line" }));
    clean.forEach(point => {
      const selected = point.item.player_id === selectedId;
      const tooltip = `${personName(point.item)} · ${teamName(point.item)} · ${formatValue(point.y)} gols · ${formatValue(point.x)} xG · ${formatValue(point.item.minutes_played)} min · ${formatValue(point.item.shots)} finalizações`;
      const circle = svgNode("circle", {
        cx: xAt(point.x), cy: yAt(point.y), r: selected ? 8 : 5,
        class: `player-scatter-point${selected ? " is-selected" : ""}`,
        tabindex: "0", role: "button", "aria-pressed": String(selected), "aria-label": tooltip,
      });
      if (onSelect) {
        circle.addEventListener("click", () => onSelect(point.item));
        circle.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(point.item); }
        });
      }
      svg.append(attachChartTooltip(circle, tooltip));
    });
    svg.append(svgNode("text", { x: width / 2, y: height - 2, class: "chart-axis-title", "text-anchor": "middle" }, "xG"));
    svg.append(svgNode("text", { x: 13, y: height / 2, class: "chart-axis-title", transform: `rotate(-90 13 ${height / 2})`, "text-anchor": "middle" }, "Gols"));
    return node("div", { class: "svg-chart player-scatter-chart" }, svg);
  }

  function playerOverviewTable(rows, { selectedId = null, onSelect = null } = {}) {
    const ordered = [...rows].sort((left, right) => (number(right.minutes_played) || 0) - (number(left.minutes_played) || 0));
    const columns = [
      ["Jogador", player => node("span", { class: "players-table-player" }, [flagNode(player.team_name), node("strong", { text: personName(player) })])],
      ["Seleção", player => displayTeamName(player.team_name)], ["Pos.", player => positionLabel(player.position)],
      ["Min.", player => formatValue(player.minutes_played)], ["Gols", player => formatValue(player.goals)],
      ["xG", player => formatValue(player.xg)], ["Finalizações", player => formatValue(player.shots)],
      ["Rating", player => formatValue(player.rating)],
    ];
    const body = ordered.slice(0, 250).map(player => {
      const row = node("tr", { class: player.player_id === selectedId ? "is-selected" : "", tabindex: "0" }, columns.map(([, render]) => node("td", {}, render(player))));
      row.onclick = () => onSelect?.(player);
      row.onkeydown = event => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect?.(player); }
      };
      return row;
    });
    return node("div", { class: "table-wrap players-overview-table", tabindex: "0", role: "region", "aria-label": "Jogadores filtrados" }, [
      node("table", {}, [node("thead", {}, node("tr", {}, columns.map(([labelText]) => node("th", { scope: "col", text: labelText })))), node("tbody", {}, body)]),
    ]);
  }

  function playerProfileView(data, activeTab = "general") {
    if (!data?.available) return emptyState("Sem dados neste recorte", data?.notice || "Escolha outro recorte para continuar.");
    const player = data.player || data.summary || {};
    const conversion = number(player.shots) ? (number(player.goals) || 0) / number(player.shots) * 100 : null;
    const summary = [
      ["Posição", positionLabel(player.position)], ["Minutos", player.minutes_played], ["Gols", player.goals],
      ["Assistências", player.assists], ["xG", player.xg], ["Finalizações", player.shots],
      ["Conversão", conversion === null ? null : `${formatValue(conversion)}%`], ["Rating médio", player.rating],
    ].filter(([, value]) => value !== null && value !== undefined);
    let content;
    if (activeTab === "radar") {
      content = node("div", { class: "player-profile-radar" }, [
        radarChart(data.radar || player.radar || [], `${personName(player)} no recorte selecionado`),
        node("p", { text: "Percentis calculados contra jogadores da mesma função no recorte selecionado." }),
      ]);
    } else if (activeTab === "shots") {
      content = playerShotMapPanel(data.shot_map || []);
    } else if (activeTab === "distribution") {
      content = node("div", { class: "player-distribution-stack" }, [
        playerShotMinuteChart(data.shot_map || []),
        playerShotDistributions(data.shot_map || []),
      ]);
    } else {
      content = node("div", { class: "player-profile-general" }, [
        node("p", { class: "player-profile-note", text: `${formatValue(player.games)} jogos no recorte · precisão de passe ${metricAvailable(player.pass_accuracy) ? `${formatValue(player.pass_accuracy)}%` : "não disponível"}.` }),
        playerMatchLogTable(data.match_log || []),
      ]);
    }
    return node("article", { class: "player-profile-view" }, [
      node("header", { class: "player-profile-identity" }, [flagNode(player.team_name, "flag-large"), node("span", {}, [node("small", { text: displayTeamName(player.team_name) }), node("h3", { text: personName(player) })])]),
      node("dl", { class: "player-profile-summary" }, summary.map(([labelText, value]) => node("div", {}, [node("dt", { text: labelText }), node("dd", { text: formatValue(value) })]))),
      node("div", { class: "player-profile-content" }, content),
    ]);
  }

  function playerMatchLogTable(logs) {
    if (!logs.length) return emptyState("Jogos indisponíveis", "Não há atuações registradas neste recorte.");
    return node("div", { class: "table-wrap player-match-log" }, [node("table", {}, [
      node("thead", {}, node("tr", {}, ["Partida", "Min.", "Gols", "xG", "Finalizações", "Rating"].map(labelText => node("th", { text: labelText })))),
      node("tbody", {}, logs.map(log => node("tr", {}, [
        node("td", { text: translateTeamsInText(log.match) }), node("td", { text: formatValue(log.minutes_played) }),
        node("td", { text: formatValue(log.goals) }), node("td", { text: formatValue(log.xg) }),
        node("td", { text: formatValue(log.shots) }), node("td", { text: formatValue(log.rating) }),
      ]))),
    ])]);
  }

  function playerShotMapPanel(shots) {
    if (!shots.length) return emptyState("Mapa de finalizações indisponível", "Não há chutes registrados neste recorte.");
    const state = { mode: "all", body: "all", type: "all" };
    const output = node("div");
    const modes = [["all", "Todos"], ["goals", "Gols"], ["on_target", "No alvo"], ["high_xg", "xG alto"]];
    const buttons = modes.map(([key, labelText]) => node("button", { type: "button", text: labelText, onclick: () => { state.mode = key; draw(); } }));
    const bodySelect = node("select", {}, [node("option", { value: "all", text: "Todas" }), ...[...new Set(shots.map(shot => shot.body_part).filter(Boolean))].map(value => node("option", { value, text: BODY_PART_LABELS[String(value).toLowerCase()] || label(value) }))]);
    const typeSelect = node("select", {}, [node("option", { value: "all", text: "Todas" }), ...[...new Set(shots.map(shot => shot.shot_type).filter(Boolean))].map(value => node("option", { value, text: SHOT_TYPE_LABELS[String(value).toLowerCase()] || label(value) }))]);
    const controls = node("div", { class: "player-shot-controls" }, [
      node("div", { class: "segmented-control" }, buttons),
      node("label", {}, [node("span", { text: "Parte do corpo" }), bodySelect]),
      node("label", {}, [node("span", { text: "Situação" }), typeSelect]),
    ]);
    function draw() {
      buttons.forEach((button, index) => button.classList.toggle("is-active", modes[index][0] === state.mode));
      const filtered = shots.filter(shot => {
        const xg = number(shot.xg ?? shot.statsbomb_xg) || 0;
        return (state.mode === "all" || (state.mode === "goals" && shot.is_goal) || (state.mode === "on_target" && shot.is_on_target) || (state.mode === "high_xg" && xg >= .2))
          && (state.body === "all" || shot.body_part === state.body)
          && (state.type === "all" || shot.shot_type === state.type);
      });
      const normalized = filtered.map(shot => {
        const away = shot.team_name && shot.team_name === shot.away_team;
        return { ...shot, x: away && number(shot.x) !== null ? 120 - number(shot.x) : shot.x, home_team: shot.team_name, away_team: null };
      });
      output.replaceChildren(shotMap(normalized));
    }
    bodySelect.onchange = event => { state.body = event.target.value; draw(); };
    typeSelect.onchange = event => { state.type = event.target.value; draw(); };
    draw();
    return node("div", { class: "player-shot-analysis" }, [controls, output]);
  }

  function playerShotMinuteChart(shots) {
    if (!shots.length) return emptyState("Distribuição temporal indisponível", "Não há finalizações neste recorte.");
    const ranges = [[0, 15], [16, 30], [31, 45], [46, 60], [61, 75], [76, 90], [91, Infinity]];
    const bins = ranges.map(([start, end]) => {
      const rows = shots.filter(shot => (number(shot.minute) || 0) >= start && (number(shot.minute) || 0) <= end);
      return { label: end === Infinity ? "90+" : `${start}-${end}`, shots: rows.length, goals: rows.filter(shot => shot.is_goal).length, xg: rows.reduce((total, shot) => total + (number(shot.xg ?? shot.statsbomb_xg) || 0), 0) };
    });
    const width = 720, height = 250, pad = 40, max = Math.max(...bins.map(bin => bin.shots), 1), barWidth = (width - pad * 2) / bins.length;
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Finalizações por faixa de minuto" });
    bins.forEach((bin, index) => {
      const h = bin.shots / max * (height - pad * 2);
      const x = pad + index * barWidth + 8, y = height - pad - h;
      const bar = svgNode("rect", { x, y, width: barWidth - 16, height: h, rx: 2, class: "player-minute-bar", tabindex: "0" });
      svg.append(attachChartTooltip(bar, `${bin.label} min · ${bin.shots} finalizações · ${bin.goals} gols · ${formatValue(bin.xg)} xG`));
      if (bin.goals) svg.append(svgNode("circle", { cx: x + (barWidth - 16) / 2, cy: Math.max(pad, y - 7), r: 4 + bin.goals, class: "player-minute-goal" }));
      svg.append(svgNode("text", { x: x + (barWidth - 16) / 2, y: height - 16, class: "chart-axis", "text-anchor": "middle" }, bin.label));
    });
    return node("article", { class: "player-distribution-panel" }, [node("h3", { text: "Finalizações por minuto" }), node("div", { class: "svg-chart" }, svg)]);
  }

  function playerShotDistributions(shots) {
    if (!shots.length) return null;
    const distributions = [
      ["Parte do corpo", shots.map(shot => BODY_PART_LABELS[String(shot.body_part || "").toLowerCase()] || "Outros")],
      ["Situação da finalização", shots.map(shot => SHOT_TYPE_LABELS[String(shot.shot_type || "").toLowerCase()] || "Outras")],
    ];
    return node("div", { class: "player-distribution-grid" }, distributions.map(([title, values]) => {
      const counts = [...values.reduce((map, value) => map.set(value, (map.get(value) || 0) + 1), new Map()).entries()].sort((a, b) => b[1] - a[1]);
      const max = Math.max(...counts.map(([, value]) => value), 1);
      return node("article", { class: "player-distribution-panel" }, [node("h3", { text: title }), node("div", { class: "player-distribution-bars" }, counts.map(([labelText, value]) => node("div", { class: "player-distribution-row", title: `${labelText}: ${value}` }, [
        node("span", { text: labelText }), node("span", { class: "player-distribution-track" }, node("span", { style: `width:${value / max * 100}%` })), node("strong", { text: value }),
      ])))]);
    }));
  }

  function renderMatches(data) {
    const fragment = dashboardShell("Partida por partida", "Resultados, placares e distribuição do calendário por fase.", data);
    const metrics = kpis(data.summary || {}, ["matches", "goals", "goals_per_match"]);
    if (metrics) fragment.append(metrics);
    if (data.stage_distribution?.length) {
      fragment.append(section("Distribuição por fase", `${data.stage_distribution.length} fases`,
        node("article", { class: "chart-card chart-card-wide" }, horizontalBars(data.stage_distribution, "matches", { name: item => item.stage, limit: 12 }))
      ));
    }
    if (data.items?.length) {
      const selected = { group: "all", stage: "all", team: "all", status: "all" };
      const filters = data.filters || {};
      const controls = node("div", { class: "analysis-filters match-filters" }, [
        filterSelect("Grupo", "group", filters.groups || []),
        filterSelect("Fase", "stage", filters.stages || []),
        filterSelect("Seleção", "team", filters.teams || []),
        filterSelect("Status", "status", filters.statuses || []),
      ]);
      const grid = node("div", { class: "score-grid" });
      const meta = node("span", { text: `${data.items.length} partidas` });
      const matchSection = section("Calendário", "", node("div", {}, [controls, grid]));
      matchSection.querySelector(".section-heading").append(meta);
      fragment.append(matchSection);

      function filterSelect(labelText, key, values) {
        return node("label", {}, [
          node("span", { text: labelText }),
          node("select", { onchange: event => { selected[key] = event.target.value; drawMatches(); } }, [
            node("option", { value: "all", text: "Todos" }),
          ...values.map(value => node("option", { value, text: key === "team" ? displayTeamName(value) : value })),
          ]),
        ]);
      }

      function drawMatches() {
        const rows = data.items.filter(match => {
          const teams = [match.home_team, match.away_team];
          return (selected.group === "all" || match.group_name === selected.group)
            && (selected.stage === "all" || match.stage === selected.stage)
            && (selected.team === "all" || teams.includes(selected.team))
            && (selected.status === "all" || match.status === selected.status);
        });
        meta.textContent = `${rows.length} partidas`;
        grid.replaceChildren(...rows.slice(0, 96).map(matchCard));
      }
      drawMatches();
    }
    if (!metrics && !data.items?.length) fragment.append(emptyState());
    els.view.replaceChildren(fragment);
  }

  function renderShots(data) {
    const fragment = dashboardShell("Finalizações e xG", "Onde as chances nasceram, quem finalizou e como cada tentativa terminou.", data);
    const shots = data.shot_map || [];
    const matches = [...new Map(shots.filter(item => item.match_id !== undefined).map(item => [
      String(item.match_id),
      {
        id: String(item.match_id),
        label: `${displayTeamName(first(item, ["home_team"], "Mandante"))} ${formatValue(item.home_score)}–${formatValue(item.away_score)} ${displayTeamName(first(item, ["away_team"], "Visitante"))}`,
      },
    ])).values()];
    const selected = { match: matches[0]?.id || "all", team: "all" };
    const filters = node("div", { class: "analysis-filters" }, [
      node("label", {}, [
        node("span", { text: "Partida" }),
        node("select", {
          onchange: event => {
            selected.match = event.target.value;
            selected.team = "all";
            updateTeamOptions();
            drawAnalysis();
          },
        }, [
          node("option", { value: "all", text: "Todas as partidas" }),
          ...matches.map(match => node("option", { value: match.id, text: match.label, selected: match.id === selected.match })),
        ]),
      ]),
      node("label", {}, [
        node("span", { text: "Equipe" }),
        node("select", { onchange: event => { selected.team = event.target.value; drawAnalysis(); } }),
      ]),
    ]);
    const matchSelect = filters.querySelectorAll("select")[0];
    const teamSelect = filters.querySelectorAll("select")[1];
    const analysis = node("div", { class: "analysis-stack" });
    fragment.append(filters, analysis);

    function matchShots() {
      return selected.match === "all"
        ? shots
        : shots.filter(item => String(item.match_id) === selected.match);
    }
    function updateTeamOptions() {
      const teams = [...new Set(matchShots().map(item => item.team_name).filter(Boolean))].sort();
      teamSelect.replaceChildren(
        node("option", { value: "all", text: "Todas as equipes" }),
        ...teams.map(team => node("option", { value: team, text: displayTeamName(team) }))
      );
      teamSelect.value = selected.team;
    }
    function drawAnalysis() {
      const byMatch = matchShots();
      const filtered = selected.team === "all"
        ? byMatch
        : byMatch.filter(item => item.team_name === selected.team);
      const goals = filtered.filter(item => item.is_goal).length;
      const xg = filtered.reduce((total, item) => total + (number(item.statsbomb_xg) || 0), 0);
      const players = new Set(filtered.map(item => item.player_name).filter(Boolean)).size;
      const blocks = [
        kpis({ shots: filtered.length, goals, xg: Math.round(xg * 100) / 100, players }),
        section("Mapa de finalizações", `${filtered.length} chutes`, shotMap(filtered), "wide-chart"),
      ];
      if (selected.match !== "all") {
        const flow = (data.xg_flow || []).filter(item => String(item.match_id) === selected.match);
        blocks.push(section("Fluxo de xG", "Evolução da partida", xgFlowPlot(flow), "wide-chart"));
      }
      analysis.replaceChildren(...blocks.filter(Boolean));
    }
    matchSelect.value = selected.match;
    updateTeamOptions();
    drawAnalysis();

    if (data.player_leaders?.length) {
      const metric = data.player_leaders.some(item => item.xg !== undefined) ? "xg" : "shots";
      fragment.append(section("Jogadores mais perigosos", "Top 12",
        node("article", { class: "chart-card chart-card-wide" }, horizontalBars(data.player_leaders, metric, { name: personName, limit: 12 }))
      ));
    }
    const breakdowns = entries(data.breakdowns || {}).filter(([, rows]) => rows?.length);
    if (breakdowns.length) {
      fragment.append(section("Perfil das finalizações", `${breakdowns.length} distribuições`,
        node("div", { class: "chart-grid" }, breakdowns.map(([key, rows]) => node("article", { class: "chart-card" }, [
          node("div", { class: "chart-card-head" }, [node("p", { class: "eyebrow", text: "Distribuição" }), node("h3", { text: metricName(key) })]),
          horizontalBars(rows, "value", { name: item => item.label, limit: 8 }),
        ])))
      ));
    }
    els.view.replaceChildren(fragment);
  }

  function renderOfficialMetrics(data) {
    const fragment = dashboardShell("Métricas oficiais FIFA", "Leitura espelhada do confronto e das fases de jogo publicadas nos relatórios oficiais.", data);
    if (data.scoreboard) fragment.append(section("Placar do relatório", "Partida analisada", scoreCard(data.scoreboard)));
    if (data.team_comparison?.length) {
      fragment.append(section("Comparação entre equipes", `${data.team_comparison.length} métricas`, mirroredComparison(data.team_comparison)));
    }
    if (data.phase_comparison?.length) {
      fragment.append(section("Fases de jogo", `${data.phase_comparison.length} fases`, mirroredComparison(data.phase_comparison, true)));
    }
    const leaders = rankingPanels(data.player_leaders || {}, { entity: "player", maxPanels: 6, valueKey: "value" });
    if (leaders) fragment.append(section("Líderes do relatório", `${entries(data.player_leaders).length} métricas`, leaders));
    if (!data.scoreboard && !data.team_comparison?.length && !data.phase_comparison?.length && !leaders) fragment.append(emptyState());
    els.view.replaceChildren(fragment);
  }

  function substitutionEntryMinutes(side, events = []) {
    const team = side?.team_name;
    const enteredMinutes = new Map();
    events.filter(event => event.type === "substitution" && event.team_name === team && event.player_name).forEach(event => {
      enteredMinutes.set(event.player_name, number(event.minute));
    });
    return enteredMinutes;
  }

  function makePlayerSurfaceInteractive(element, player, beforeOpen = null) {
    if (!player) return element;
    element.classList.add("is-player-interactive");
    element.tabIndex = 0;
    element.setAttribute("role", "button");
    element.setAttribute("aria-label", `Ver estatísticas de ${player.player_name}`);
    const activate = event => {
      if (event.type === "click" && event.target !== element && event.target.closest("button, a, summary, select")) return;
      beforeOpen?.();
      openPlayerModal(player);
    };
    element.addEventListener("click", activate);
    element.addEventListener("keydown", event => {
      if (event.target === element && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        activate(event);
      }
    });
    return element;
  }

  function matchLineupPlayer(player, teamNameValue, matchPlayers) {
    const playerId = player.id || player.player_id;
    const playerName = player.name || player.player_name;
    return matchPlayers.find(candidate =>
      (playerId && candidate.player_id === playerId)
      || (playerName && candidate.player_name === playerName && candidate.team_name === teamNameValue)
    ) || null;
  }

  function lineupPlayerRow(player, className = "", detail = null, matchPlayer = null) {
    const row = node("li", { class: className }, [
      node("span", { class: "shirt-number", text: player.jersey_number || "–" }),
      node("strong", { text: player.name || player.player_name }),
      detail
        ? node("span", { class: "lineup-entry-detail", text: detail })
        : node("span", { text: positionLabel(player.position) }),
    ]);
    return makePlayerSurfaceInteractive(row, matchPlayer);
  }

  function lineupPanel(side, matchPlayers = [], events = []) {
    if (!side) return null;
    const players = side.starting_xi || [];
    const subs = side.substitutes || [];
    const enteredMinutes = substitutionEntryMinutes(side, events);
    return node("article", { class: "lineup-card" }, [
      node("div", { class: "chart-card-head" }, [
        node("p", { class: "eyebrow", text: side.formation ? `Formação ${side.formation}` : "Escalação" }),
        node("h3", {}, side.team_name ? teamLabel(side.team_name) : "Equipe"),
      ]),
      node("ol", { class: "lineup-list" }, players.map(player => lineupPlayerRow(
        player,
        "",
        null,
        matchLineupPlayer(player, side.team_name, matchPlayers),
      ))),
      subs.length ? node("details", { class: "data-disclosure lineup-subs" }, [
        node("summary", {}, [node("span", { text: "Banco de reservas" }), node("strong", { text: `${subs.length} jogadores` })]),
        node("ol", { class: "lineup-list" }, subs.map(player => {
          const name = player.name || player.player_name;
          const entered = enteredMinutes.get(name);
          return lineupPlayerRow(
            player,
            entered !== undefined ? "lineup-player-used" : "",
            entered !== undefined ? `Entrou ${formatValue(entered)}'` : null,
            matchLineupPlayer(player, side.team_name, matchPlayers),
          );
        })),
      ]) : null,
    ]);
  }

  function sortedEvents(rows) {
    return [...rows].sort((left, right) => {
      const leftSequence = number(left?.sequence);
      const rightSequence = number(right?.sequence);
      if (leftSequence !== null && rightSequence !== null) return leftSequence - rightSequence;
      return (number(left?.minute) || 0) - (number(right?.minute) || 0)
        || (number(left?.extra_time) || 0) - (number(right?.extra_time) || 0);
    });
  }

  function eventLabel(type) {
    return EVENT_LABELS[String(type || "").toLowerCase()] || "Lance da partida";
  }

  function eventMinute(event) {
    const minute = number(event?.minute);
    if (minute === null) return "—";
    return `${formatValue(minute)}${number(event?.extra_time) ? `+${formatValue(event.extra_time)}` : ""}'`;
  }

  function eventDescription(event) {
    const type = String(event?.type || "").toLowerCase();
    const player = event?.player_name || null;
    if (type === "goal") return player || "Gol confirmado";
    return [event?.team_name ? displayTeamName(event.team_name) : null, player].filter(Boolean).join(" · ") || "Lance registrado";
  }

  function eventTimeline(rows, className = "") {
    return node("ol", { class: `event-timeline ${className}`.trim() }, rows.map(event => {
      const type = String(event?.type || "").toLowerCase();
      return node("li", { class: `event-item event-${type.replace(/[^a-z0-9_-]/g, "")}` }, [
        node("time", { text: eventMinute(event) }),
        node("span", { class: "event-icon", text: EVENT_ICONS[type] || "·", "aria-hidden": "true" }),
        node("div", { class: "event-copy" }, [
          node("strong", { text: eventLabel(type) }),
          node("span", { text: eventDescription(event) }),
        ]),
      ]);
    }));
  }

  function pluralCount(value, singular, plural) {
    return value ? `${value} ${value === 1 ? singular : plural}` : null;
  }

  function momentsSummary(rows) {
    const counts = rows.reduce((result, event) => {
      const type = String(event?.type || "").toLowerCase();
      result[type] = (result[type] || 0) + 1;
      return result;
    }, {});
    return [
      pluralCount(counts.goal, "gol", "gols"),
      pluralCount(counts.shot_on_target, "chute no alvo", "chutes no alvo"),
      pluralCount((counts.yellow_card || 0) + (counts.red_card || 0), "cartão", "cartões"),
      pluralCount(counts.substitution, "substituição", "substituições"),
      pluralCount(counts.var, "revisão do VAR", "revisões do VAR"),
      pluralCount(counts.penalty, "pênalti", "pênaltis"),
    ].filter(Boolean).join(" · ");
  }

  function reconciledMatchEvents(rows, match) {
    const events = [...(rows || [])];
    const goalMinutes = new Set(events
      .filter(event => String(event?.type).toLowerCase() === "goal")
      .map(event => number(event?.minute))
      .filter(minute => minute !== null));
    (match?.goals || []).forEach(goal => {
      const minute = number(goal?.minute);
      if (minute !== null && goalMinutes.has(minute)) return;
      events.push({
        minute,
        extra_time: goal?.extra_time,
        type: "goal",
        team_name: goal?.team_name,
        player_name: goal?.player_name,
      });
      if (minute !== null) goalMinutes.add(minute);
    });
    return sortedEvents(events);
  }

  function matchMoments(rows, match) {
    const complete = sortedEvents(rows || []);
    const ordered = reconciledMatchEvents(rows, match);
    if (!ordered.length) return emptyState("Eventos ainda não disponíveis para esta partida.");
    const narrative = ordered.filter(event => NARRATIVE_EVENT_TYPES.has(String(event?.type || "").toLowerCase()));
    const primary = narrative.length ? narrative : ordered.slice(0, 8);
    return node("div", { class: "match-moments" }, [
      node("p", { class: "moments-summary", text: momentsSummary(ordered) || `${ordered.length} lances registrados` }),
      eventTimeline(primary, "event-timeline-summary"),
      complete.length ? node("details", { class: "moments-disclosure" }, [
        node("summary", {}, [
          node("span", { text: "Ver timeline completa" }),
          node("strong", { text: `${complete.length} eventos` }),
        ]),
        eventTimeline(complete, "event-timeline-complete"),
      ]) : null,
    ]);
  }

  function endpointStatus(rows) {
    if (!rows?.length) return null;
    return node("ul", { class: "endpoint-grid" }, rows.map(row => node("li", { class: row.fetch_status === "success" ? "is-available" : "is-unavailable" }, [
      node("strong", { text: row.endpoint_name }),
      node("span", { text: `${row.fetch_status || "unknown"} · HTTP ${formatValue(row.http_status)}` }),
    ])));
  }

  function matchCenterHero(match) {
    return node("header", { class: "match-center-hero" }, [
      scoreCard(match, { hero: true }),
    ]);
  }

  function matchSubnav() {
    const links = [
      ["Resumo", "#match-summary"],
      ["Finalizações & xG", "#match-finalizations"],
      ["Jogadores", "#match-players"],
      ["Momentos", "#match-moments"],
      ["Escalações", "#match-lineups"],
    ];
    return node("nav", { class: "match-subnav", "aria-label": "Navegação da partida" }, links.map(([labelText, href]) =>
      node("a", { href, text: labelText })
    ));
  }

  function matchStoryPanel(story = []) {
    return node("article", { class: "story-card" }, story.length
      ? node("ul", { class: "story-list" }, story.slice(0, 5).map(line => node("li", { text: translateTeamsInText(line) })))
      : node("p", { text: "A história da partida aparecerá quando houver estatísticas suficientes." })
    );
  }

  function comparisonBars(rows, className = "") {
    if (!rows?.length) return emptyState("Visão geral indisponível", "As métricas comparativas ainda não estão disponíveis para esta partida.");
    return node("div", { class: `comparison-stack ${className}`.trim() }, rows.map(row => {
      const title = `${metricName(row.metric)} · ${displayTeamName(row.home_team)}: ${formatValue(row.home_value)} · ${displayTeamName(row.away_team)}: ${formatValue(row.away_value)}`;
      return node("div", {
        class: "comparison-row",
        tabIndex: 0,
        "aria-label": title,
        "data-tooltip": title,
        style: matchPalette(row.home_team, row.away_team),
      }, [
        node("strong", { class: "comparison-value", text: formatValue(row.home_value) }),
        node("div", { class: "comparison-main" }, [
          node("span", { class: "comparison-label", text: metricName(row.metric) }),
          node("div", { class: "comparison-track" }, [
            node("span", {
              class: "comparison-fill home",
              style: `--bar-size:${Math.max(2, row.home_pct || 0)}%`,
            }),
            node("span", {
              class: "comparison-fill away",
              style: `--bar-size:${Math.max(2, row.away_pct || 0)}%`,
            }),
          ]),
        ]),
        node("strong", { class: "comparison-value", text: formatValue(row.away_value) }),
      ]);
    }));
  }

  function unifiedComparisonRows(data, match) {
    const home = match?.home_team || "Mandante";
    const away = match?.away_team || "Visitante";
    const rows = [];
    const seen = new Set();
    (data.comparison_bars || []).forEach(row => {
      if (!row?.metric || seen.has(row.metric)) return;
      seen.add(row.metric);
      rows.push(row.metric === "expected_goals" ? {
        ...row,
        home_value: Math.max(0, number(row.home_value) || 0),
        away_value: Math.max(0, number(row.away_value) || 0),
      } : row);
    });
    (data.stats_comparison || []).forEach(row => {
      if (!row?.metric || seen.has(row.metric)) return;
      let homeValue = number(row[home]);
      let awayValue = number(row[away]);
      if (homeValue === null && awayValue === null) return;
      if (row.metric === "expected_goals") {
        homeValue = Math.max(0, homeValue || 0);
        awayValue = Math.max(0, awayValue || 0);
      }
      const maximum = Math.max(Math.abs(homeValue || 0), Math.abs(awayValue || 0), 1);
      seen.add(row.metric);
      rows.push({
        metric: row.metric,
        home_team: home,
        away_team: away,
        home_value: homeValue,
        away_value: awayValue,
        home_pct: Math.abs(homeValue || 0) / maximum * 100,
        away_pct: Math.abs(awayValue || 0) / maximum * 100,
      });
    });
    return rows;
  }

  function matchOverview(data, match) {
    const rows = unifiedComparisonRows(data, match);
    if (!rows.length) return emptyState("Visão geral ainda não disponível para esta partida.");
    const byMetric = new Map(rows.map(row => [row.metric, row]));
    const groups = [
      ["Ataque", ["expected_goals", "total_shots", "shots_on_target"]],
      ["Posse & passe", ["ball_possession", "passes", "accurate_passes"]],
      ["Defesa", ["ball_recoveries", "tackles", "interceptions"]],
      ["Disciplina", ["fouls", "yellow_cards", "red_cards"]],
    ].map(([title, metrics]) => [title, metrics.map(metric => byMetric.get(metric)).filter(Boolean)])
      .filter(([, metrics]) => metrics.length);
    const primary = groups.length
      ? node("div", { class: "overview-groups" }, groups.map(([title, metrics]) =>
          node("article", { class: "overview-group" }, [
            node("h3", { text: title }),
            comparisonBars(metrics, "comparison-stack-compact"),
          ])
        ))
      : comparisonBars(rows.slice(0, 10));
    return node("div", { class: "match-overview-content" }, [
      primary,
      rows.length > 10 ? node("details", { class: "overview-disclosure" }, [
        node("summary", {}, [
          node("span", { text: "Ver métricas completas" }),
          node("strong", { text: `${rows.length} indicadores` }),
        ]),
        comparisonBars(rows, "comparison-stack-secondary"),
      ]) : null,
    ]);
  }

  function defensiveActions(player) {
    return (number(player?.tackles) || 0)
      + (number(player?.interceptions) || 0)
      + (number(player?.clearances) || 0)
      + (number(player?.recoveries) || 0);
  }

  function impactMetricLine(player) {
    return [
      number(player.goals) ? pluralCount(number(player.goals), "gol", "gols") : null,
      number(player.xg) ? `${formatValue(player.xg)} xG` : null,
      number(player.xa) ? `${formatValue(player.xa)} xA` : null,
      number(player.shots) ? pluralCount(number(player.shots), "chute", "chutes") : null,
      number(player.key_passes) ? pluralCount(number(player.key_passes), "passe-chave", "passes-chave") : null,
      number(player.accurate_passes) ? `${formatValue(player.accurate_passes)} passes certos` : null,
      defensiveActions(player) ? `${formatValue(defensiveActions(player))} ações defensivas` : null,
      number(player.rating) ? `rating ${formatValue(player.rating)}` : null,
    ].filter(Boolean).slice(0, 3).join(" · ") || "Participação registrada na partida";
  }

  function impactPanel(players, matchPlayers = []) {
    return node("div", { class: "impact-section" }, [
      node("p", { class: "section-intro", text: "Índice contextual 0–100 calculado pelas dimensões disponíveis para a função." }),
      node("div", { class: "card-grid" }, players.slice(0, 3).map((player, index) => {
        const fullPlayer = matchPlayers.find(candidate => candidate.player_id === player.player_id)
          || matchPlayers.find(candidate => candidate.player_name === player.player_name && candidate.team_name === player.team_name);
        const card = node("article", { class: "card impact-card" }, [
          node("span", { class: "card-kicker", text: `#${index + 1}` }),
          node("h3", { text: player.player_name }),
          node("p", { class: "impact-role", text: [player.team_name ? displayTeamName(player.team_name) : null, positionLabel(player.position)].filter(Boolean).join(" · ") }),
          node("strong", { class: "impact-inline-score", text: `${formatValue(player.impact_score)}/100` }),
          node("p", { class: "impact-metrics", text: impactMetricLine(player) }),
        ]);
        return makePlayerSurfaceInteractive(card, fullPlayer);
      })),
    ]);
  }

  function xgContext(data, match) {
    const teams = [match?.home_team, match?.away_team].filter(Boolean);
    if (!teams.length || !data.shot_map?.length) return null;
    const shotTotals = Object.fromEntries(teams.map(team => [team, 0]));
    data.shot_map.forEach(shot => {
      if (shotTotals[shot.team_name] === undefined) return;
      shotTotals[shot.team_name] += Math.max(0, number(shot.xg ?? shot.statsbomb_xg) || 0);
    });
    const official = (data.stats_comparison || []).find(row => row.metric === "expected_goals");
    const byShot = teams.map(team => `${displayTeamName(team)} ${formatValue(Math.round(shotTotals[team] * 100) / 100)} xG`).join(" · ");
    if (!official) return `Fluxo por chute: ${byShot}.`;
    const officialValues = Object.fromEntries(teams.map(team => [team, Math.max(0, number(official[team]) || 0)]));
    const differs = teams.some(team => Math.abs(officialValues[team] - shotTotals[team]) >= 0.01);
    if (!differs) return `xG acumulado dos chutes: ${byShot}.`;
    const overview = teams.map(team => `${displayTeamName(team)} ${formatValue(officialValues[team])} xG`).join(" · ");
    return `Fluxo por chute: ${byShot}. Visão geral: ${overview}.`;
  }

  function finalizationsPanel(data, match) {
    const context = xgContext(data, match);
    return node("div", { class: "finalizations-stack" }, [
      node("article", { class: "finalizations-panel" }, [
        node("div", { class: "subsection-heading" }, [
          node("h3", { text: "Mapa de chutes" }),
          data.shot_map?.length ? node("span", { text: `${data.shot_map.length} chutes` }) : null,
        ]),
        data.shot_map?.length
          ? interactiveShotMap(data.shot_map)
          : emptyState("Mapa de chutes ainda não disponível para esta partida."),
      ]),
      node("article", { class: "finalizations-panel" }, [
        node("div", { class: "subsection-heading" }, node("h3", { text: "Fluxo de xG" })),
        context ? node("p", { class: "xg-context", text: context }) : null,
        data.xg_flow?.length
          ? xgFlowPlot(data.xg_flow)
          : emptyState("Fluxo de xG ainda não disponível para esta partida."),
      ]),
    ]);
  }

  function radarChart(profile = [], title = "Radar do jogador") {
    const axes = profile.filter(item => item?.value !== undefined && item?.value !== null);
    if (axes.length < 3) return emptyState("Radar indisponível", "Este jogador ainda não tem dimensões suficientes para uma comparação contextual.");
    const size = 260;
    const center = size / 2;
    const radius = 82;
    const axisLabel = axis => RADAR_LABELS[axis?.axis] || RADAR_LABELS[axis?.abbr] || axis?.axis || "Métrica";
    const points = axes.map((axis, index) => {
      const angle = -Math.PI / 2 + index * (Math.PI * 2 / axes.length);
      const valueRadius = radius * Math.max(0, Math.min(100, number(axis.value) || 0)) / 100;
      return {
        axis,
        angle,
        labelX: center + Math.cos(angle) * (radius + 28),
        labelY: center + Math.sin(angle) * (radius + 28),
        x: center + Math.cos(angle) * valueRadius,
        y: center + Math.sin(angle) * valueRadius,
        gridX: center + Math.cos(angle) * radius,
        gridY: center + Math.sin(angle) * radius,
      };
    });
    const svg = svgNode("svg", { viewBox: `0 0 ${size} ${size}`, role: "img", "aria-label": title });
    svg.append(svgNode("title", {}, title));
    [0.33, 0.66, 1].forEach(scale => {
      const ring = points.map(point => `${center + Math.cos(point.angle) * radius * scale},${center + Math.sin(point.angle) * radius * scale}`).join(" ");
      svg.append(svgNode("polygon", { points: ring, class: "radar-ring" }));
    });
    points.forEach(point => {
      svg.append(svgNode("line", { x1: center, y1: center, x2: point.gridX, y2: point.gridY, class: "radar-axis" }));
      svg.append(svgNode("text", { x: point.labelX, y: point.labelY + 3, class: "radar-label", "text-anchor": point.labelX < center - 8 ? "end" : point.labelX > center + 8 ? "start" : "middle" }, axisLabel(point.axis)));
    });
    svg.append(svgNode("polygon", { points: points.map(point => `${point.x},${point.y}`).join(" "), class: "radar-area" }));
    points.forEach(point => {
      const tooltip = `${axisLabel(point.axis)}: ${formatValue(point.axis.value)}/100 · Comparação com jogadores de função semelhante`;
      const dot = svgNode("circle", { cx: point.x, cy: point.y, r: 3.5, class: "radar-dot", tabindex: "0", "aria-label": tooltip });
      svg.append(attachChartTooltip(dot, tooltip));
    });
    return node("div", { class: "radar-wrap" }, svg);
  }

  const metricAvailable = value => value !== null && value !== undefined && value !== "";

  function percentWithVolume(value, numerator, denominator) {
    if (!metricAvailable(value) || !metricAvailable(numerator) || !metricAvailable(denominator) || number(denominator) <= 0) return null;
    return `${formatValue(value)}% (${formatValue(numerator)}/${formatValue(denominator)})`;
  }

  function modalMetric(labelText, value) {
    if (!metricAvailable(value)) return null;
    return { label: labelText, value: typeof value === "number" ? formatValue(value) : value };
  }

  function modalStatSection(title, metrics) {
    const available = metrics.filter(Boolean);
    if (!available.length) return null;
    return node("section", { class: "player-modal-section" }, [
      node("h3", { text: title }),
      node("dl", { class: "player-modal-stats" }, available.map(metric => node("div", {}, [
        node("dt", { text: metric.label }),
        node("dd", { text: metric.value }),
      ]))),
    ]);
  }

  function hasPositiveMetrics(player, keys) {
    return keys.some(key => metricAvailable(player[key]) && number(player[key]) > 0);
  }

  function playerPerformanceStory(player) {
    const accuracy = metricAvailable(player.pass_accuracy) && number(player.passes) > 0
      ? `${formatValue(player.pass_accuracy)}% de precisão em ${formatValue(player.passes)} passes`
      : null;
    const duels = number(player.duels_won) > 0 ? `${formatValue(player.duels_won)} duelos vencidos` : null;
    const defensive = defensiveActions(player) > 0 ? `${formatValue(defensiveActions(player))} ações defensivas` : null;
    const creation = [
      number(player.assists) > 0 ? `${formatValue(player.assists)} ${number(player.assists) === 1 ? "assistência" : "assistências"}` : null,
      number(player.key_passes) > 0 ? `${formatValue(player.key_passes)} ${number(player.key_passes) === 1 ? "passe para finalização" : "passes para finalização"}` : null,
    ].filter(Boolean).join(" e ");
    if (player.macroposition === "Goleiro") {
      const parts = [number(player.saves) > 0 ? `${formatValue(player.saves)} defesas` : null, accuracy, metricAvailable(player.rating) ? `rating ${formatValue(player.rating)}` : null].filter(Boolean);
      return parts.length ? `Atuação no gol marcada por ${parts.join(", ")}.` : `Atuação de ${formatValue(player.minutes_played)} minutos no gol.`;
    }
    if (["Volante/Meio-campista", "Meia ofensivo/Ponta"].includes(player.macroposition)) {
      const parts = [accuracy, creation || null, duels].filter(Boolean);
      return parts.length ? `Atuação de circulação e ligação: ${parts.join(", ")}.` : `Participação de ${formatValue(player.minutes_played)} minutos no meio-campo.`;
    }
    if (["Zagueiro", "Lateral/Ala"].includes(player.macroposition)) {
      const parts = [defensive, duels, accuracy].filter(Boolean);
      return parts.length ? `Atuação defensiva sustentada por ${parts.join(", ")}.` : `Participação de ${formatValue(player.minutes_played)} minutos no sistema defensivo.`;
    }
    const attack = [
      number(player.goals) > 0 ? `${formatValue(player.goals)} ${number(player.goals) === 1 ? "gol" : "gols"}` : null,
      number(player.shots) > 0 ? `${formatValue(player.shots)} finalizações` : null,
      number(player.shots_on_target) > 0 ? `${formatValue(player.shots_on_target)} no alvo` : null,
      metricAvailable(player.xg) ? `${formatValue(player.xg)} xG` : null,
    ].filter(Boolean);
    return attack.length ? `Presença ofensiva: ${attack.join(", ")}.` : `Partida de baixo volume ofensivo em ${formatValue(player.minutes_played)} minutos.`;
  }

  function playerContextComparisons(player) {
    const cohort = (state.matchPlayers || []).filter(item => number(item.minutes_played) > 0);
    const sameFunction = cohort.filter(item => item.macroposition === player.macroposition);
    const comparisons = [];
    if (metricAvailable(player.profile_score) && sameFunction.length > 1) {
      const ordered = [...sameFunction].filter(item => metricAvailable(item.profile_score)).sort((a, b) => number(b.profile_score) - number(a.profile_score));
      const rank = ordered.findIndex(item => item.player_id === player.player_id) + 1;
      if (rank > 0) comparisons.push({ value: `#${rank} de ${ordered.length}`, label: "entre jogadores da mesma função na partida" });
    }
    const strongest = [...(player.radar || [])].filter(axis => metricAvailable(axis.value)).sort((a, b) => number(b.value) - number(a.value))[0];
    if (strongest) {
      const peers = sameFunction.map(item => (item.radar || []).find(axis => axis.axis === strongest.axis)?.value).filter(metricAvailable).map(number);
      const average = peers.length ? peers.reduce((total, value) => total + value, 0) / peers.length : null;
      const relation = average === null ? null : number(strongest.value) >= average + 3 ? "Acima da média da função" : number(strongest.value) <= average - 3 ? "Abaixo da média da função" : "Na média da função";
      comparisons.push({ value: `${strongest.axis}: ${formatValue(strongest.value)}/100`, label: relation || "Melhor dimensão contextual" });
    }
    const rankingMetric = player.macroposition === "Centroavante"
      ? ["xg", "xG"]
      : player.macroposition === "Goleiro"
        ? ["saves", "defesas"]
        : ["accurate_passes", "passes certos"];
    if (metricAvailable(player[rankingMetric[0]])) {
      const teamPlayers = cohort.filter(item => item.team_name === player.team_name && metricAvailable(item[rankingMetric[0]])).sort((a, b) => number(b[rankingMetric[0]]) - number(a[rankingMetric[0]]));
      const rank = teamPlayers.findIndex(item => item.player_id === player.player_id) + 1;
      if (rank > 0) comparisons.push({ value: rank === 1 ? `Líder em ${rankingMetric[1]}` : `#${rank} em ${rankingMetric[1]}`, label: displayTeamName(player.team_name) });
    }
    return comparisons.slice(0, 3);
  }

  function playerDetailedSections(player) {
    const passing = [
      modalMetric("Passes", player.passes),
      modalMetric("Passes certos", metricAvailable(player.accurate_passes) && metricAvailable(player.passes) ? `${formatValue(player.accurate_passes)}/${formatValue(player.passes)}` : null),
      modalMetric("Precisão de passe", percentWithVolume(player.pass_accuracy, player.accurate_passes, player.passes)),
      modalMetric("Passes longos", metricAvailable(player.accurate_long_balls) && metricAvailable(player.total_long_balls) ? `${formatValue(player.accurate_long_balls)}/${formatValue(player.total_long_balls)}` : null),
      modalMetric("Precisão de passe longo", percentWithVolume(player.long_pass_accuracy, player.accurate_long_balls, player.total_long_balls)),
      modalMetric("Cruzamentos", metricAvailable(player.accurate_crosses) && metricAvailable(player.total_crosses) ? `${formatValue(player.accurate_crosses)}/${formatValue(player.total_crosses)}` : null),
      modalMetric("Precisão nos cruzamentos", percentWithVolume(player.cross_accuracy, player.accurate_crosses, player.total_crosses)),
    ];
    const attack = hasPositiveMetrics(player, ["goals", "xg", "shots", "shots_on_target", "shots_off_target", "blocked_shots"])
      ? modalStatSection("Ataque", [
        modalMetric("Gols", player.goals),
        modalMetric("xG", player.xg),
        modalMetric("Finalizações", player.shots),
        modalMetric("No alvo", player.shots_on_target),
        modalMetric("Para fora", player.shots_off_target),
        modalMetric("Bloqueadas", player.blocked_shots),
        modalMetric("xG por chute", player.xg_per_shot),
      ])
      : null;
    const creation = hasPositiveMetrics(player, ["assists", "xa", "key_passes", "big_chances_created"])
      ? modalStatSection("Criação", [
        modalMetric("Assistências", player.assists),
        modalMetric("xA", player.xa),
        modalMetric("Passes para finalização", player.key_passes),
        modalMetric("Grandes chances criadas", player.big_chances_created),
      ])
      : null;
    const defense = hasPositiveMetrics(player, ["tackles", "interceptions", "clearances", "recoveries"])
      ? modalStatSection("Defesa", [
        modalMetric("Desarmes", player.tackles),
        modalMetric("Interceptações", player.interceptions),
        modalMetric("Cortes", player.clearances),
        modalMetric("Recuperações", player.recoveries),
      ])
      : null;
    const duels = hasPositiveMetrics(player, ["duels_won", "aerial_won"])
      ? modalStatSection("Duelos", [
        modalMetric("Duelos vencidos", player.duels_won),
        modalMetric("Duelos aéreos vencidos", player.aerial_won),
      ])
      : null;
    const dribbles = hasPositiveMetrics(player, ["successful_dribbles"])
      ? modalStatSection("Drible", [
        modalMetric("Dribles completos", player.successful_dribbles),
        modalMetric("Perdas da posse", player.dispossessed),
      ])
      : null;
    const discipline = hasPositiveMetrics(player, ["fouls", "fouls_suffered", "yellow_cards", "red_cards", "offsides"])
      ? modalStatSection("Disciplina", [
        modalMetric("Faltas cometidas", player.fouls),
        modalMetric("Faltas sofridas", player.fouls_suffered),
        modalMetric("Cartões amarelos", player.yellow_cards),
        modalMetric("Cartões vermelhos", player.red_cards),
        modalMetric("Impedimentos", player.offsides),
      ])
      : null;
    const sections = player.macroposition === "Goleiro"
      ? [
        modalStatSection("Goleiro", [
          modalMetric("Defesas", player.saves),
          modalMetric("Toques", player.touches),
          modalMetric("Cortes", player.clearances),
          modalMetric("Recuperações", player.recoveries),
        ]),
        modalStatSection("Distribuição", passing),
      ]
      : [
        attack,
        creation,
        number(player.passes) > 0 ? modalStatSection("Passe", passing) : null,
        defense,
        duels,
        dribbles,
        discipline,
      ];
    return sections.filter(Boolean);
  }

  function playerQuickMetrics(player) {
    const contextual = metricAvailable(player.profile_score) ? `${formatValue(player.profile_score)}/100` : null;
    const base = [
      modalMetric("Minutos", player.minutes_played),
      modalMetric("Perfil contextual", contextual),
      modalMetric("Rating", player.rating),
    ];
    let priorities;
    if (player.macroposition === "Goleiro") {
      priorities = [
        modalMetric("Defesas", player.saves),
        modalMetric("Passes certos", player.accurate_passes),
        modalMetric("Precisão de passe", percentWithVolume(player.pass_accuracy, player.accurate_passes, player.passes)),
      ];
    } else if (["Volante/Meio-campista", "Meia ofensivo/Ponta"].includes(player.macroposition)) {
      priorities = [
        modalMetric("Passes certos", player.accurate_passes),
        modalMetric("Precisão de passe", percentWithVolume(player.pass_accuracy, player.accurate_passes, player.passes)),
        modalMetric("xA", player.xa),
        modalMetric("Passes para finalização", player.key_passes),
        modalMetric("Duelos vencidos", player.duels_won),
        modalMetric("Ações defensivas", defensiveActions(player)),
      ];
    } else if (["Zagueiro", "Lateral/Ala"].includes(player.macroposition)) {
      priorities = [
        modalMetric("Ações defensivas", defensiveActions(player)),
        modalMetric("Desarmes", player.tackles),
        modalMetric("Interceptações", player.interceptions),
        modalMetric("Cortes", player.clearances),
        modalMetric("Duelos vencidos", player.duels_won),
        modalMetric("Passes certos", player.accurate_passes),
      ];
    } else {
      priorities = [
        modalMetric("Gols", player.goals),
        modalMetric("xG", player.xg),
        modalMetric("Finalizações", player.shots),
        modalMetric("No alvo", player.shots_on_target),
        modalMetric("xA", player.xa),
        modalMetric("Assistências", player.assists),
      ];
    }
    const metrics = [...base, ...priorities];
    return metrics.filter(Boolean);
  }

  function playerRadarPanel(player) {
    const dimensions = (player.radar || []).filter(axis => metricAvailable(axis.value));
    if (dimensions.length < 3) return emptyState("Radar indisponível", "As estatísticas desta partida não permitem uma comparação contextual consistente para este jogador.");
    const comparisons = playerContextComparisons(player);
    return node("div", { class: "player-modal-radar" }, [
      radarChart(dimensions, `${player.player_name} na partida`),
      node("div", { class: "player-context-copy" }, [
        comparisons.length ? node("ul", { class: "player-context-list" }, comparisons.map(item => node("li", {}, [
          node("strong", { text: item.value }),
          node("span", { text: item.label }),
        ]))) : null,
        node("p", { class: "player-context-note", text: "O perfil contextual compara a produção do jogador com atletas de função semelhante." }),
      ]),
    ]);
  }

  function performanceHighlight(title, headline, detail = null) {
    return node("article", { class: "performance-highlight" }, [
      node("span", { text: title }),
      node("strong", { text: headline }),
      detail ? node("p", { text: detail }) : null,
    ]);
  }

  function playerPerformanceHighlights(player) {
    const candidates = [];
    if (number(player.passes) > 0 && metricAvailable(player.accurate_passes)) {
      candidates.push({
        key: "pass",
        node: performanceHighlight(
          "Passe",
          `${formatValue(player.accurate_passes)}/${formatValue(player.passes)} passes certos`,
          metricAvailable(player.pass_accuracy) ? `${formatValue(player.pass_accuracy)}% de precisão` : null,
        ),
      });
    }
    if (hasPositiveMetrics(player, ["goals", "shots", "xg", "shots_on_target"])) {
      const headline = [
        number(player.goals) > 0 ? `${formatValue(player.goals)} ${number(player.goals) === 1 ? "gol" : "gols"}` : null,
        number(player.shots) > 0 ? `${formatValue(player.shots)} finalizações` : null,
      ].filter(Boolean).join(" · ");
      const detail = [
        metricAvailable(player.xg) ? `${formatValue(player.xg)} xG` : null,
        number(player.shots_on_target) > 0 ? `${formatValue(player.shots_on_target)} no alvo` : null,
      ].filter(Boolean).join(" · ");
      candidates.push({ key: "attack", node: performanceHighlight("Ataque", headline, detail) });
    }
    if (hasPositiveMetrics(player, ["assists", "xa", "key_passes", "big_chances_created"])) {
      const headline = [
        number(player.assists) > 0 ? `${formatValue(player.assists)} ${number(player.assists) === 1 ? "assistência" : "assistências"}` : null,
        number(player.key_passes) > 0 ? `${formatValue(player.key_passes)} ${number(player.key_passes) === 1 ? "passe para finalização" : "passes para finalização"}` : null,
      ].filter(Boolean).join(" · ") || `${formatValue(player.xa)} xA`;
      const detail = number(player.big_chances_created) > 0 ? `${formatValue(player.big_chances_created)} ${number(player.big_chances_created) === 1 ? "grande chance criada" : "grandes chances criadas"}` : metricAvailable(player.xa) ? `${formatValue(player.xa)} xA` : null;
      candidates.push({ key: "creation", node: performanceHighlight("Criação", headline, detail) });
    }
    if (hasPositiveMetrics(player, ["tackles", "interceptions", "clearances", "recoveries"])) {
      const parts = [
        number(player.tackles) > 0 ? pluralCount(number(player.tackles), "desarme", "desarmes") : null,
        number(player.interceptions) > 0 ? pluralCount(number(player.interceptions), "interceptação", "interceptações") : null,
        number(player.clearances) > 0 ? pluralCount(number(player.clearances), "corte", "cortes") : null,
      ].filter(Boolean);
      candidates.push({ key: "defense", node: performanceHighlight("Defesa", `${formatValue(defensiveActions(player))} ações defensivas`, parts.join(" · ")) });
    }
    if (hasPositiveMetrics(player, ["duels_won", "aerial_won"])) {
      candidates.push({
        key: "duels",
        node: performanceHighlight(
          "Disputa",
          `${formatValue(player.duels_won)} duelos vencidos`,
          number(player.aerial_won) > 0 ? `${formatValue(player.aerial_won)} pelo alto` : null,
        ),
      });
    }
    if (player.macroposition === "Goleiro" && metricAvailable(player.saves)) {
      candidates.unshift({ key: "goalkeeping", node: performanceHighlight("Defesa do gol", `${formatValue(player.saves)} defesas`, metricAvailable(player.rating) ? `Rating ${formatValue(player.rating)}` : null) });
    }
    const priority = player.macroposition === "Centroavante"
      ? ["attack", "creation", "duels", "pass"]
      : player.macroposition === "Goleiro"
        ? ["goalkeeping", "pass", "defense"]
        : ["pass", "creation", "defense", "duels", "attack"];
    const ordered = priority.map(key => candidates.find(item => item.key === key)).filter(Boolean).slice(0, 3);
    if (!ordered.length) return null;
    return node("section", { class: "player-modal-section" }, [
      node("h3", { text: "Destaques da atuação" }),
      node("div", { class: "performance-highlights" }, ordered.map(item => item.node)),
    ]);
  }

  function playerShotsPanel(player) {
    const shots = player.player_shots || [];
    if (!shots.length) return null;
    return node("section", { class: "player-modal-section player-actions-section" }, [
      node("h3", { text: "Finalizações" }),
      shotMap(shots),
      node("ol", { class: "player-shot-list" }, shots.map(shot => node("li", {}, [
        node("time", { text: `${formatValue(shot.minute)}'` }),
        node("strong", { text: SHOT_OUTCOME_LABELS[String(shot.shot_outcome || "").toLowerCase()] || "Finalização" }),
        modalMetric("", shot.xg)?.value ? node("span", { text: `${formatValue(shot.xg)} xG` }) : null,
        shot.body_part ? node("span", { text: BODY_PART_LABELS[String(shot.body_part).toLowerCase()] || shot.body_part }) : null,
      ]))),
    ]);
  }

  function playerEventsPanel(player) {
    const events = sortedEvents(player.player_events || []).slice(0, 10);
    if (!events.length) return null;
    return node("section", { class: "player-modal-section" }, [
      node("h3", { text: "Eventos principais" }),
      eventTimeline(events, "player-event-timeline"),
    ]);
  }

  function openPlayerModal(player) {
    document.querySelector(".player-modal")?.remove();
    const entry = (player.player_events || []).find(event => String(event.type).toLowerCase() === "substitution");
    const quickMetrics = playerQuickMetrics(player);
    const minutesWarning = number(player.minutes_played) < 30;
    const dialog = node("dialog", { class: "player-modal", "aria-labelledby": "player-modal-title" });
    const close = () => {
      document.body.classList.remove("modal-open");
      dialog.close();
      dialog.remove();
    };
    const closeButton = node("button", { type: "button", class: "player-modal-close", text: "Fechar", onclick: close });
    const headerFacts = [
      player.started === true ? "Titular" : player.started === false ? "Reserva" : null,
      entry ? `Entrou ${eventMinute(entry)}` : null,
      metricAvailable(player.goals) ? `${formatValue(player.goals)} ${number(player.goals) === 1 ? "gol" : "gols"}` : null,
      metricAvailable(player.assists) ? `${formatValue(player.assists)} ${number(player.assists) === 1 ? "assistência" : "assistências"}` : null,
      metricAvailable(player.yellow_cards) && number(player.yellow_cards) > 0 ? `${formatValue(player.yellow_cards)} amarelo` : null,
      metricAvailable(player.red_cards) && number(player.red_cards) > 0 ? `${formatValue(player.red_cards)} vermelho` : null,
    ].filter(Boolean);
    const content = [
      node("header", { class: "player-modal-header" }, [
        node("div", { class: "player-modal-identity" }, [
          flagNode(player.team_name, "flag-large"),
          node("div", {}, [
            node("p", { class: "eyebrow", text: displayTeamName(player.team_name) }),
            node("h2", { id: "player-modal-title", text: player.player_name }),
            node("p", { class: "player-modal-role", text: `${positionLabel(player.position)} · ${player.macroposition || "Posição não informada"}` }),
          ]),
        ]),
        closeButton,
        headerFacts.length ? node("p", { class: "player-modal-facts", text: headerFacts.join(" · ") }) : null,
        node("p", { class: "player-modal-story", text: playerPerformanceStory(player) }),
      ]),
      minutesWarning ? node("p", { class: "player-modal-warning", text: "Poucos minutos: interprete o perfil com cautela." }) : null,
      node("section", { class: "player-modal-section" }, [
        node("h3", { text: "Resumo da atuação" }),
        node("dl", { class: "player-quick-grid" }, quickMetrics.map(metric => node("div", {}, [node("dt", { text: metric.label }), node("dd", { text: metric.value })]))),
      ]),
      node("section", { class: "player-modal-section" }, [
        node("div", { class: "player-modal-section-head" }, [
          node("h3", { text: "Perfil contextual" }),
          node("span", { text: player.macroposition || "Função" }),
        ]),
        playerRadarPanel(player),
      ]),
      playerPerformanceHighlights(player),
      node("div", { class: "player-modal-section-grid" }, playerDetailedSections(player)),
      playerShotsPanel(player),
      playerEventsPanel(player),
    ].filter(Boolean);
    dialog.append(node("div", { class: "player-modal-shell" }, content));
    dialog.addEventListener("click", event => {
      if (event.target === dialog) close();
    });
    dialog.addEventListener("cancel", event => {
      event.preventDefault();
      close();
    });
    document.body.append(dialog);
    document.body.classList.add("modal-open");
    dialog.showModal();
    closeButton.focus();
  }

  function playerExplorer(players = []) {
    const rows = players.filter(player => player.player_id && number(player.minutes_played) > 0);
    if (!rows.length) return emptyState("Jogadores indisponíveis", "As estatísticas individuais ainda não estão disponíveis para esta partida.");
    let selected = rows[0];
    let sort = { key: "impact_score", direction: "desc" };
    const detail = node("article", { class: "player-detail-card" });
    const tbody = node("tbody");
    const thead = node("thead");
    const columns = [
      { key: "player_name", label: "Jogador", value: player => player.player_name, render: player => node("span", {
        class: "player-name-button",
        text: player.player_name,
      }) },
      { key: "team_name", label: "Time", value: player => displayTeamName(player.team_name), render: player => teamLabel(player.team_name) },
      { key: "position", label: "Pos.", value: player => positionLabel(player.position) },
      { key: "minutes_played", label: "Min.", value: player => number(player.minutes_played) },
      { key: "impact_score", label: "Impacto", value: player => number(player.impact_score) },
      { key: "xg", label: "xG", value: player => number(player.xg) },
      { key: "xa", label: "xA", value: player => number(player.xa) },
      { key: "accurate_passes", label: "Passes", value: player => number(player.accurate_passes) },
      { key: "defensive_actions", label: "Ações defensivas", value: player => defensiveActions(player) },
      { key: "rating", label: "Rating", value: player => number(player.rating) },
    ];
    const table = node("div", { class: "table-wrap player-table-wrap", tabindex: "0", role: "region", "aria-label": "Tabela de jogadores da partida" }, [
      node("table", { class: "player-metrics-table" }, [
        thead,
        tbody,
      ]),
    ]);

    function sortedRows() {
      const column = columns.find(item => item.key === sort.key) || columns[0];
      return [...rows].sort((left, right) => {
        const leftValue = column.value(left);
        const rightValue = column.value(right);
        if ((leftValue === null || leftValue === undefined) && (rightValue === null || rightValue === undefined)) return 0;
        if (leftValue === null || leftValue === undefined) return 1;
        if (rightValue === null || rightValue === undefined) return -1;
        const comparison = typeof leftValue === "number" && typeof rightValue === "number"
          ? leftValue - rightValue
          : String(leftValue).localeCompare(String(rightValue), "pt-BR", { sensitivity: "base", numeric: true });
        return sort.direction === "asc" ? comparison : -comparison;
      });
    }

    function drawHeader() {
      thead.replaceChildren(node("tr", {}, columns.map(column => {
        const active = sort.key === column.key;
        return node("th", { scope: "col", "aria-sort": active ? (sort.direction === "asc" ? "ascending" : "descending") : "none" },
          node("button", {
            type: "button",
            class: `sort-button${active ? " is-active" : ""}`,
            onclick: () => {
              sort = sort.key === column.key
                ? { key: column.key, direction: sort.direction === "asc" ? "desc" : "asc" }
                : { key: column.key, direction: typeof column.value(rows[0]) === "number" ? "desc" : "asc" };
              drawHeader();
              drawRows();
            },
          }, [
            node("span", { text: column.label }),
            node("span", { class: "sort-indicator", text: active ? (sort.direction === "asc" ? "↑" : "↓") : "↕", "aria-hidden": "true" }),
          ])
        );
      })));
    }

    function playerSummary(player) {
      return [
        player.minutes_played !== null && player.minutes_played !== undefined ? `${formatValue(player.minutes_played)} minutos` : null,
        number(player.shots) ? pluralCount(number(player.shots), "chute", "chutes") : null,
        number(player.accurate_passes) ? `${formatValue(player.accurate_passes)} passes certos` : null,
        defensiveActions(player) ? `${formatValue(defensiveActions(player))} ações defensivas` : null,
      ].filter(Boolean).join(" · ") || "Participação individual registrada na partida.";
    }

    function drawDetail() {
      detail.replaceChildren(
        node("div", { class: "player-detail-head" }, [
          node("div", {}, [
            node("p", { class: "eyebrow", text: selected.team_name ? displayTeamName(selected.team_name) : "Jogador" }),
            node("h3", {}, node("button", { type: "button", class: "player-name-button", text: selected.player_name, onclick: () => openPlayerModal(selected) })),
            node("span", { class: "pill", text: positionLabel(selected.position) }),
          ]),
          node("strong", { class: "impact-score", text: `${formatValue(selected.impact_score)}/100` }),
        ]),
        radarChart(selected.radar || [], `${selected.player_name} na partida`),
        node("p", { class: "player-summary", text: playerSummary(selected) }),
        node("button", { type: "button", class: "action-link player-detail-action", text: "Ver estatísticas completas", onclick: () => openPlayerModal(selected) }),
        node("dl", { class: "feature-stats compact" }, [
          ["Gols", selected.goals],
          ["xG", selected.xg],
          ["xA", selected.xa],
          ["Passes certos", selected.accurate_passes],
          ["Precisão passe", selected.pass_accuracy !== null && selected.pass_accuracy !== undefined ? `${formatValue(selected.pass_accuracy)}%` : null],
          ["Ações defensivas", defensiveActions(selected)],
        ].map(([key, value]) => node("div", {}, [node("dt", { text: key }), node("dd", { text: formatValue(value) })])))
      );
    }

    function drawRows() {
      tbody.replaceChildren(...sortedRows().map(player => {
        const tr = node("tr", {
          class: player.player_id === selected.player_id ? "is-selected" : "",
          title: `${player.player_name} · impacto ${formatValue(player.impact_score)}/100`,
        }, columns.map(column => column.render
          ? node("td", {}, column.render(player))
          : node("td", { text: formatValue(column.value(player)) })
        ));
        return makePlayerSurfaceInteractive(tr, player, () => {
            selected = player;
            drawRows();
            drawDetail();
        });
      }));
    }

    drawHeader();
    drawRows();
    drawDetail();
    return node("div", { class: "player-explorer" }, [table, detail]);
  }

  function interactiveShotMap(rows = []) {
    const selected = { team: "all", player: "all", mode: "all", shot: null };
    const modeLabels = { goals: "Somente gols", on_target: "No alvo", high_xg: "xG alto" };
    const teams = [...new Set(rows.map(row => row.team_name).filter(Boolean))].sort();
    const players = [...new Set(rows.map(row => row.player_name).filter(Boolean))].sort();
    const output = node("div", { class: "analysis-stack" });
    const controls = node("div", { class: "shot-controls" }, [
      node("div", { class: "segmented-control" }, [
        shotButton("Todos", "all"),
        shotButton("Somente gols", "goals"),
        shotButton("No alvo", "on_target"),
        shotButton("xG alto", "high_xg"),
      ]),
      node("label", {}, [
        node("span", { text: "Seleção" }),
        node("select", { onchange: event => { selected.team = event.target.value; draw(); } }, [
          node("option", { value: "all", text: "Todos" }),
          ...teams.map(team => node("option", { value: team, text: displayTeamName(team) })),
        ]),
      ]),
      node("label", {}, [
        node("span", { text: "Jogador" }),
        node("select", { onchange: event => { selected.player = event.target.value; draw(); } }, [
          node("option", { value: "all", text: "Todos os jogadores" }),
          ...players.map(player => node("option", { value: player, text: player })),
        ]),
      ]),
    ]);

    function shotButton(labelText, mode) {
      return node("button", {
        type: "button",
        class: mode === selected.mode ? "is-active" : "",
        text: labelText,
        "aria-pressed": mode === selected.mode ? "true" : "false",
        onclick: event => {
          selected.mode = mode;
          controls.querySelectorAll(".segmented-control button").forEach(button => {
            const active = button === event.currentTarget;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
          });
          draw();
        },
      });
    }

    function filteredShots() {
      return rows.filter(shot => {
        const xg = number(shot.statsbomb_xg) || 0;
        return (selected.team === "all" || shot.team_name === selected.team)
          && (selected.player === "all" || shot.player_name === selected.player)
          && (selected.mode === "all"
            || (selected.mode === "goals" && shot.is_goal)
            || (selected.mode === "on_target" && shot.is_on_target)
            || (selected.mode === "high_xg" && xg >= 0.15));
      });
    }

    function draw() {
      const filtered = filteredShots();
      let selectedShot = filtered.find(shot => shotKey(shot) === selected.shot) || null;
      if (!selectedShot) selected.shot = null;
      const goals = filtered.filter(shot => shot.is_goal).length;
      const xg = Math.round(filtered.reduce((total, shot) => total + Math.max(0, number(shot.statsbomb_xg) || 0), 0) * 100) / 100;
      const activeFilters = [
        selected.mode !== "all" ? modeLabels[selected.mode] : null,
        selected.team !== "all" ? displayTeamName(selected.team) : null,
        selected.player !== "all" ? selected.player : null,
      ].filter(Boolean);
      const summary = activeFilters.length
        ? `Exibindo ${filtered.length} de ${rows.length} chutes · ${goals} gols · ${formatValue(xg)} xG`
        : `${filtered.length} chutes · ${goals} gols · ${formatValue(xg)} xG`;
      const content = [
        activeFilters.length ? node("p", { class: "shot-filter-status", text: `Filtro ativo: ${activeFilters.join(" · ")}` }) : null,
        node("p", { class: "shot-summary", text: summary }),
        shotMap(filtered, {
          selectedKey: selected.shot,
          onSelect: shot => {
            selected.shot = shotKey(shot);
            draw();
          },
        }),
        selectedShot ? shotDetail(selectedShot) : null
      ].filter(Boolean);
      output.replaceChildren(...content);
    }

    draw();
    return node("div", { class: "interactive-shot-map" }, [controls, output]);
  }

  function renderTheStatsApiMatch(data) {
    const match = data.match || {};
    state.matchPlayers = data.players || [];
    document.body.classList.add("is-match-center");
    const fragment = document.createDocumentFragment();
    fragment.append(matchCenterHero(match));
    fragment.append(matchSubnav());
    const message = first(data, ["notice", "message", "warning"]);
    if (message && !technicalTextPattern.test(message)) fragment.append(node("aside", { class: "notice", text: message }));
    fragment.append(section("História do jogo", null, matchStoryPanel(data.match_story || []), "", "match-summary"));
    if (data.player_impacts?.length) {
      fragment.append(section("Top impactos da partida", null, impactPanel(data.player_impacts, data.players || [])));
    }
    fragment.append(section("Visão geral da partida", null, matchOverview(data, match), "wide-chart match-overview"));
    fragment.append(section("Finalizações & xG", null, finalizationsPanel(data, match), "wide-chart finalizations-section", "match-finalizations"));
    fragment.append(section("Jogadores da partida", null, playerExplorer(data.players || []), "wide-chart", "match-players"));
    fragment.append(section("Momentos do jogo", null, matchMoments(data.events || [], match), "", "match-moments"));
    const lineups = [
      lineupPanel(data.lineups?.home, data.players || [], data.events || []),
      lineupPanel(data.lineups?.away, data.players || [], data.events || []),
    ].filter(Boolean);
    if (lineups.length) fragment.append(section("Escalações", "Titulares e banco", node("div", { class: "lineup-grid" }, lineups), "", "match-lineups"));
    els.view.replaceChildren(fragment);
  }

  function renderAvailability(data) {
    els.view.replaceChildren(emptyState("Área indisponível", "Escolha uma das áreas esportivas no menu principal."));
  }

  const GROUP_STAT_DEFINITIONS = {
    "Pos": "posição atual no grupo.",
    "J": "jogos disputados.",
    "V": "vitórias.",
    "E": "empates.",
    "D": "derrotas.",
    "GP": "gols pró, total de gols marcados.",
    "GC": "gols contra, total de gols sofridos.",
    "SG": "saldo de gols, gols pró menos gols contra.",
    "Pts": "pontos conquistados.",
  };

  function closeStatPopover() {
    state.statPopover?.remove();
    state.statPopover = null;
  }

  function teamGroupStatBreakdown(team, matches, statKey) {
    const teamId = team?.team_id;
    const teamNameValue = rawTeamName(team);
    const totals = {
      J: team?.played,
      V: team?.wins,
      E: team?.draws,
      D: team?.losses,
      GP: team?.goals_for,
      GC: team?.goals_against,
      SG: team?.goal_difference,
      Pts: team?.points,
    };
    const items = (matches || []).flatMap(match => {
      const isHome = (teamId && match.home_team_id === teamId) || match.home_team === teamNameValue;
      const isAway = (teamId && match.away_team_id === teamId) || match.away_team === teamNameValue;
      const homeScore = number(match.home_score);
      const awayScore = number(match.away_score);
      if ((!isHome && !isAway) || homeScore === null || awayScore === null) return [];
      const goalsFor = isHome ? homeScore : awayScore;
      const goalsAgainst = isHome ? awayScore : homeScore;
      const opponentName = isHome ? match.away_team : match.home_team;
      const opponentId = isHome ? match.away_team_id : match.home_team_id;
      const won = goalsFor > goalsAgainst;
      const drew = goalsFor === goalsAgainst;
      const resultLabel = won ? "Vitória" : drew ? "Empate" : "Derrota";
      const points = won ? 3 : drew ? 1 : 0;
      const values = {
        J: 1,
        V: won ? 1 : 0,
        E: drew ? 1 : 0,
        D: !won && !drew ? 1 : 0,
        GP: goalsFor,
        GC: goalsAgainst,
        SG: goalsFor - goalsAgainst,
        Pts: points,
      };
      if (["V", "E", "D"].includes(statKey) && values[statKey] === 0) return [];
      return [{
        matchId: match.match_id,
        opponentId,
        opponentName,
        matchLabel: `${displayTeamName(teamNameValue)} x ${displayTeamName(opponentName)}`,
        scoreLabel: `${goalsFor}–${goalsAgainst}`,
        dateLabel: formatMatchDate(match.match_date),
        value: values[statKey],
        resultLabel,
      }];
    });
    return {
      teamId,
      teamName: teamNameValue,
      group: team?.group_name,
      statKey,
      totalValue: totals[statKey],
      items,
    };
  }

  function statBreakdownLine(item, statKey) {
    const opponent = displayTeamName(item.opponentName);
    if (statKey === "GP") return `${formatValue(item.value)} vs ${opponent}`;
    if (statKey === "GC") return `${formatValue(item.value)} sofrido(s) vs ${opponent}`;
    if (statKey === "SG") return `${item.scoreLabel} vs ${opponent} → ${signedStandingValue(item.value)}`;
    if (statKey === "Pts") return `${item.resultLabel} vs ${opponent} → +${formatValue(item.value)}`;
    return `${item.scoreLabel} vs ${opponent}`;
  }

  function placeFloatingPopover(anchor, popover) {
    document.body.append(popover);
    const rect = anchor.getBoundingClientRect();
    const popoverRect = popover.getBoundingClientRect();
    const left = Math.max(10, Math.min(rect.left, window.innerWidth - popoverRect.width - 10));
    const below = rect.bottom + 8;
    const top = below + popoverRect.height < window.innerHeight
      ? below
      : Math.max(10, rect.top - popoverRect.height - 8);
    popover.style.left = `${left}px`;
    popover.style.top = `${top}px`;
    state.statPopover = popover;
  }

  function showStatPopover(anchor, breakdown) {
    closeStatPopover();
    const definition = GROUP_STAT_DEFINITIONS[breakdown.statKey] || "Métrica da campanha no grupo.";
    const popover = node("aside", { class: "stat-popover-floating", role: "tooltip" }, [
      node("strong", { text: `${displayTeamName(breakdown.teamName)} — ${formatValue(breakdown.totalValue)} ${breakdown.statKey}` }),
      breakdown.items.length
        ? node("ul", {}, breakdown.items.map(item => node("li", { text: statBreakdownLine(item, breakdown.statKey) })))
        : node("p", { text: definition }),
    ]);
    placeFloatingPopover(anchor, popover);
  }

  function showStatDefinition(anchor, labelText, definition) {
    closeStatPopover();
    placeFloatingPopover(anchor, node("aside", { class: "stat-popover-floating", role: "tooltip" }, [
      node("strong", { text: labelText }),
      node("p", { text: definition }),
    ]));
  }

  function statCellButton(team, matches, statKey, value) {
    const breakdown = teamGroupStatBreakdown(team, matches, statKey);
    const button = node("button", {
      type: "button",
      class: "stat-cell-button",
      text: statKey === "SG" ? signedStandingValue(value) : formatValue(value),
      "aria-label": `${GROUP_STAT_DEFINITIONS[statKey]} Ver detalhamento de ${displayTeamName(rawTeamName(team))}.`,
    });
    button.addEventListener("mouseenter", () => showStatPopover(button, breakdown));
    button.addEventListener("mouseleave", closeStatPopover);
    button.addEventListener("focus", () => showStatPopover(button, breakdown));
    button.addEventListener("blur", closeStatPopover);
    button.addEventListener("click", event => {
      event.stopPropagation();
      showStatPopover(button, breakdown);
    });
    return button;
  }

  function competitionHeaderCell(labelText) {
    const definition = GROUP_STAT_DEFINITIONS[labelText];
    if (!definition) return node("th", { text: labelText, scope: "col" });
    const button = node("button", {
      type: "button",
      class: "stat-header-help",
      text: labelText,
      title: `${labelText}: ${definition}`,
      "data-tooltip": `${labelText}: ${definition}`,
      "aria-label": `${labelText}: ${definition}`,
    });
    button.addEventListener("click", event => {
      event.stopPropagation();
      showStatDefinition(button, labelText, definition);
    });
    return node("th", { scope: "col" }, button);
  }

  function closeQuickView() {
    if (!state.quickView) return;
    const returnFocus = state.quickView.returnFocus;
    document.removeEventListener("keydown", state.quickView.onKeydown);
    state.quickView.overlay.remove();
    state.quickView = null;
    document.body.classList.remove("quick-view-open");
    returnFocus?.focus?.();
  }

  function openQuickView({ kicker, titleContent, rows, extra = null, actionLabel, onAction, layout = "drawer" }) {
    closeQuickView();
    const returnFocus = document.activeElement;
    closeStatPopover();
    const onKeydown = event => {
      if (event.key === "Escape") closeQuickView();
    };
    const layoutClass = layout === "modal" ? " is-modal" : "";
    const overlay = node("div", { class: `quick-view-overlay${layoutClass}` });
    const drawer = node("aside", { class: `quick-view-drawer${layoutClass}`, role: "dialog", "aria-modal": "true", "aria-label": kicker }, [
      node("header", { class: "quick-view-head" }, [
        node("div", {}, [node("p", { class: "eyebrow", text: kicker }), node("h2", {}, titleContent)]),
        node("button", { type: "button", class: "quick-view-close", text: "×", title: "Fechar", "aria-label": "Fechar", onclick: closeQuickView }),
      ]),
      node("div", { class: "quick-view-body" }, [
        node("dl", { class: "quick-view-stats" }, rows.filter(([, value]) => value !== null && value !== undefined && value !== "").map(([key, value]) => node("div", {}, [
          node("dt", { text: key }),
          node("dd", { text: value }),
        ]))),
        extra,
      ]),
      actionLabel && onAction ? node("footer", {}, node("button", {
        type: "button",
        class: "quick-view-action",
        text: actionLabel,
        onclick: () => {
          closeQuickView();
          onAction();
        },
      })) : null,
    ]);
    overlay.append(drawer);
    overlay.addEventListener("click", event => {
      if (event.target === overlay) closeQuickView();
    });
    document.body.append(overlay);
    document.body.classList.add("quick-view-open");
    document.addEventListener("keydown", onKeydown);
    state.quickView = { overlay, onKeydown, returnFocus };
    drawer.querySelector(".quick-view-close")?.focus();
  }

  function competitionTeamContext(teamId) {
    for (const group of state.competitionData?.groups || []) {
      const team = (group.teams || []).find(item => item.team_id === teamId);
      if (team) return { team, group, matches: group.matches || [] };
    }
    return null;
  }

  function openTeamQuickView(teamNameValue, teamId) {
    const context = competitionTeamContext(teamId);
    const team = context?.team || { team_id: teamId, team_name: teamNameValue };
    const upcoming = (context?.matches || []).filter(match => match.status !== "finished" && [match.home_team_id, match.away_team_id].includes(teamId));
    const extra = upcoming.length ? node("section", { class: "quick-view-extra" }, [
      node("h3", { text: "Próximos jogos" }),
      ...upcoming.slice(0, 3).map(match => node("p", { text: `${displayTeamName(match.home_team)} × ${displayTeamName(match.away_team)} · ${formatMatchDate(match.match_date)}` })),
    ]) : null;
    openQuickView({
      kicker: "Resumo da seleção",
      titleContent: teamLabel(rawTeamName(team)),
      rows: [
        ["Grupo", team.group_name ? `Grupo ${team.group_name}` : null],
        ["Posição", team.position ? `${team.position}º` : null],
        ["Pontos", team.points],
        ["Campanha", team.played !== undefined ? `${team.wins || 0}V · ${team.draws || 0}E · ${team.losses || 0}D` : null],
        ["Gols", team.goals_for !== undefined ? `${team.goals_for} pró · ${team.goals_against} contra` : null],
        ["Saldo", team.goal_difference !== undefined ? signedStandingValue(team.goal_difference) : null],
        ["Situação", team.classification_status],
      ],
      extra,
      actionLabel: "Ver seleção completa",
      onAction: () => routeTo("teams", teamId),
    });
  }

  function quickMatchTeams(match) {
    if (match?.home && match?.away) {
      return {
        homeName: match.home.team_name || match.home.placeholder,
        awayName: match.away.team_name || match.away.placeholder,
      };
    }
    return { homeName: match?.home_team, awayName: match?.away_team };
  }

  function openMatchQuickView(match) {
    const teams = quickMatchTeams(match);
    const date = match?.match_date || match?.kickoff_at;
    const hasScore = match?.home_score !== null && match?.home_score !== undefined
      && match?.away_score !== null && match?.away_score !== undefined;
    const score = hasScore ? `${formatValue(match.home_score)}–${formatValue(match.away_score)}` : "×";
    const xg = number(match?.xg_total ?? match?.xg);
    openQuickView({
      kicker: "Resumo da partida",
      titleContent: node("span", { class: "quick-match-title" }, [
        teamLabel(teams.homeName, "quick-match-team"),
        node("strong", { text: score }),
        teamLabel(teams.awayName, "quick-match-team"),
      ]),
      rows: [
        ["Data", formatMatchDate(date)],
        ["Fase", homeStageLabel(match)],
        ["Situação", /live/i.test(match?.status || "") ? "Ao vivo" : match?.status === "finished" ? "Finalizada" : "Agendada"],
        ["xG total", xg !== null ? formatValue(xg) : null],
        ["Finalizações", match?.shots],
        ["Eventos relevantes", match?.events],
      ],
      actionLabel: "Ver partida completa",
      onAction: () => routeTo("matches", match.match_id),
    });
  }

  function competitionTeamLink(teamNameValue, teamId, className = "competition-team-link") {
    if (!teamId) return node("span", { class: className }, teamLabel(teamNameValue));
    return node("button", {
      type: "button",
      class: className,
      onclick: event => {
        event.stopPropagation();
        openTeamQuickView(teamNameValue, teamId);
      },
    }, teamLabel(teamNameValue));
  }

  function signedStandingValue(value) {
    const parsed = number(value);
    if (parsed === null) return "—";
    return parsed > 0 ? `+${formatValue(parsed)}` : formatValue(parsed);
  }

  function competitionStandingClass(team) {
    const position = number(first(team, ["position", "rank"]));
    const status = String(team?.classification_status || "").toLocaleLowerCase("pt-BR");
    if ((position !== null && position <= 2) || /classificad/.test(status)) return "competition-row-qualified";
    if (position === 3 || /possível vaga/.test(status)) return "competition-row-third";
    return "competition-row-out";
  }

  function competitionGroupTable(group) {
    const headers = ["Pos", "Seleção", "J", "V", "E", "D", "GP", "GC", "SG", "Pts"];
    return node("div", { class: "competition-table-scroll" }, node("table", { class: "competition-group-table" }, [
      node("thead", {}, node("tr", {}, headers.map(competitionHeaderCell))),
      node("tbody", {}, (group.teams || []).map((team, index) => {
        const position = first(team, ["position", "rank"], index + 1);
        const stats = [
          ["J", first(team, ["played"], 0)],
          ["V", first(team, ["wins"], 0)],
          ["E", first(team, ["draws"], 0)],
          ["D", first(team, ["losses"], 0)],
          ["GP", first(team, ["goals_for"], 0)],
          ["GC", first(team, ["goals_against"], 0)],
          ["SG", first(team, ["goal_difference"], 0)],
          ["Pts", first(team, ["points", "pts"], 0)],
        ];
        return node("tr", { class: competitionStandingClass(team) }, [
          node("td", { class: "competition-position", text: position }),
          node("td", { class: "competition-team-cell" }, [
            competitionTeamLink(rawTeamName(team), team.team_id),
            node("small", { text: team.classification_status || (position === 3 ? "Possível vaga" : "Fora agora") }),
          ]),
          ...stats.map(([statKey, value]) => node("td", {
            class: statKey === "Pts" ? "competition-points" : "",
          }, statCellButton(team, group.matches || [], statKey, value))),
        ]);
      })),
    ]));
  }

  function competitionMatchRow(match) {
    const status = String(match?.status || "").toLocaleLowerCase("pt-BR");
    const isLive = /live|ao vivo|in progress/.test(status);
    const isFinished = /finished|finalizado|encerrado/.test(status);
    const hasScore = match?.home_score !== null && match?.home_score !== undefined
      && match?.away_score !== null && match?.away_score !== undefined;
    const score = hasScore && (isFinished || isLive)
      ? `${formatValue(match.home_score)}–${formatValue(match.away_score)}`
      : "×";
    const row = node("article", {
      class: `competition-match-row${match?.match_id ? " is-clickable" : ""}`,
      role: match?.match_id ? "link" : null,
      tabIndex: match?.match_id ? 0 : -1,
      "aria-label": `${displayTeamName(match?.home_team)} ${score} ${displayTeamName(match?.away_team)}`,
    }, [
      node("div", { class: "competition-match-meta" }, [
        node("time", { dateTime: match?.match_date || "", text: isLive ? "Ao vivo" : formatMatchDate(match?.match_date) }),
        isLive ? node("span", { class: "live-label", text: "Ao vivo" }) : null,
      ]),
      node("div", { class: "competition-match-score" }, [
        competitionTeamLink(match?.home_team, match?.home_team_id),
        node("strong", { text: score }),
        competitionTeamLink(match?.away_team, match?.away_team_id),
      ]),
    ]);
    if (match?.match_id) {
      row.addEventListener("click", () => openMatchQuickView(match));
      row.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openMatchQuickView(match);
        }
      });
    }
    return row;
  }

  function competitionGroupCard(group) {
    return node("article", { class: "competition-group-card" }, [
      node("header", { class: "competition-group-head" }, [
        node("div", {}, [node("p", { class: "eyebrow", text: "Fase de grupos" }), node("h3", { text: `Grupo ${group.name}` })]),
        node("span", { text: "Pts · SG · GP · GC · Campanha" }),
      ]),
      competitionGroupTable(group),
      node("details", { class: "competition-group-games" }, [
        node("summary", {}, [
          node("span", { text: "Ver jogos do grupo" }),
          node("strong", { text: `${(group.matches || []).length} jogos` }),
          node("span", { class: "competition-chevron", text: "⌄", "aria-hidden": "true" }),
        ]),
        node("div", { class: "competition-group-matches" }, (group.matches || []).map(competitionMatchRow)),
      ]),
    ]);
  }

  function bestThirdsTable(rows) {
    const headers = ["Rank", "Grupo", "Seleção", "J", "Pts", "SG", "GP", "Status"];
    return node("div", { class: "competition-table-scroll" }, node("table", { class: "best-thirds-table" }, [
      node("thead", {}, node("tr", {}, headers.map(header => node("th", { text: header, scope: "col" })))),
      node("tbody", {}, rows.map(team => {
        const rank = number(team.rank) || 0;
        const status = rank <= 7 ? "Classificando" : rank === 8 ? "Última vaga" : "Fora agora";
        const className = rank <= 7 ? "competition-row-qualified" : rank === 8 ? "competition-row-third" : "competition-row-out";
        return node("tr", { class: className }, [
          node("td", { class: "competition-position", text: `${rank}º` }),
          node("td", { text: team.group_name || "—" }),
          node("td", { class: "competition-team-cell" }, competitionTeamLink(rawTeamName(team), team.team_id)),
          node("td", { text: formatValue(team.played) }),
          node("td", { class: "competition-points", text: formatValue(team.points) }),
          node("td", { text: signedStandingValue(team.goal_difference) }),
          node("td", { text: formatValue(team.goals_for) }),
          node("td", {}, node("span", { class: "competition-status", text: team.status || status })),
        ]);
      })),
    ]));
  }

  function knockoutTeam(side) {
    if (side?.defined) return competitionTeamLink(side.team_name, side.team_id, "knockout-team");
    return node("span", { class: "knockout-team is-placeholder", text: side?.placeholder || "Aguardando definição", title: "Aguardando definição" });
  }

  function knockoutMatchCard(match) {
    const hasScore = match?.home_score !== null && match?.home_score !== undefined
      && match?.away_score !== null && match?.away_score !== undefined;
    const card = node("article", {
      class: `knockout-match${match?.match_id ? " is-clickable" : ""}`,
      role: match?.match_id ? "link" : null,
      tabIndex: match?.match_id ? 0 : -1,
    }, [
      node("time", { dateTime: match?.kickoff_at || "", text: formatMatchDate(match?.kickoff_at) }),
      node("div", { class: "knockout-side" }, [knockoutTeam(match?.home), node("strong", { text: hasScore ? formatValue(match.home_score) : "—" })]),
      node("div", { class: "knockout-side" }, [knockoutTeam(match?.away), node("strong", { text: hasScore ? formatValue(match.away_score) : "—" })]),
    ]);
    if (match?.match_id) {
      card.addEventListener("click", () => openMatchQuickView(match));
      card.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openMatchQuickView(match);
        }
      });
    }
    return card;
  }

  function knockoutBoard(knockout) {
    return node("div", { class: "knockout-board" }, node("div", { class: "knockout-board-inner" },
      (knockout.rounds || []).map(round => node("section", { class: "knockout-round" }, [
        node("header", {}, [node("span", { text: "Fase" }), node("h3", { text: round.name })]),
        round.matches?.length
          ? node("div", { class: "knockout-round-matches" }, round.matches.map(knockoutMatchCard))
          : node("div", { class: "knockout-empty", text: "Aguardando definição" }),
      ]))
    ));
  }

  function renderCompetition(data) {
    state.competitionData = data;
    const fragment = dashboardShell("Copa do Mundo 2026", "Classificação dos grupos, melhores terceiros, jogos e caminho até a final.", data);
    const groupsView = node("div", { class: "competition-view", "data-view": "groups" });
    const knockoutView = node("div", { class: "competition-view", "data-view": "knockout", hidden: true });
    const tabs = [
      node("button", { type: "button", class: "is-active", text: "Fase de grupos", "aria-selected": "true" }),
      node("button", { type: "button", text: "Mata-mata", "aria-selected": "false" }),
    ];
    const navigation = node("nav", { class: "section-tabs competition-tabs", role: "tablist", "aria-label": "Navegação interna da competição" }, tabs);

    function selectView(view) {
      const showGroups = view === "groups";
      groupsView.hidden = !showGroups;
      knockoutView.hidden = showGroups;
      tabs[0].classList.toggle("is-active", showGroups);
      tabs[1].classList.toggle("is-active", !showGroups);
      tabs[0].setAttribute("aria-selected", String(showGroups));
      tabs[1].setAttribute("aria-selected", String(!showGroups));
    }
    tabs[0].onclick = () => selectView("groups");
    tabs[1].onclick = () => selectView("knockout");
    fragment.append(navigation);

    if (data.groups?.length) {
      groupsView.append(section("Fase de grupos", `${data.groups.length} grupos`, node("div", { class: "competition-groups-grid" }, data.groups.map(competitionGroupCard))));
    } else {
      groupsView.append(emptyState("Grupos ainda não disponíveis", "A classificação aparecerá assim que os grupos forem definidos."));
    }
    if (data.best_thirds?.length) {
      groupsView.append(section("Melhores terceiros", "8 seleções avançam", bestThirdsTable(data.best_thirds), "best-thirds-section"));
    }

    const knockout = data.knockout || {};
    knockoutView.append(section("Mata-mata", "Caminho até a final", node("div", { class: "knockout-shell" }, [
      knockout.notice ? node("p", { class: "knockout-notice", text: knockout.notice }) : null,
      knockoutBoard(knockout),
    ])));
    fragment.append(groupsView, knockoutView);
    els.view.replaceChildren(fragment);
  }

  function renderPlayerDetail(data) {
    if (!data.available) {
      els.view.replaceChildren(emptyState("Jogador não encontrado", "Ainda não encontramos esse jogador no recorte atual."));
      return;
    }
    const player = data.player || {};
    const fragment = dashboardShell(personName(player), `${teamName(player)} · ${positionLabel(player.position)}`, data);
    const metrics = kpis(data.summary || {}, ["games", "minutes_played", "goals", "assists", "shots", "xg", "xa", "rating"]);
    if (metrics) fragment.append(metrics);
    if (data.shot_map?.length) {
      fragment.append(section("Mapa de finalizações", `${data.shot_map.length} chutes`, shotMap(data.shot_map), "wide-chart"));
      fragment.append(section("Fluxo de xG", "Jogador", xgFlowPlot(data.shot_map), "wide-chart"));
    }
    els.view.replaceChildren(fragment);
  }

  function renderTeamDetail(data) {
    if (!data.available) {
      els.view.replaceChildren(emptyState("País não encontrado", "Ainda não encontramos essa seleção no recorte atual."));
      return;
    }
    const team = data.team || {};
    const fragment = dashboardShell(teamName(team), `${team.group_name || "Copa 2026"} · ${team.classification_status || "status em aberto"}`, data);
    const metrics = kpis(data.summary || {}, ["played", "wins", "draws", "losses", "points", "goals_for", "goals_against", "xg", "xga", "shots"]);
    if (metrics) fragment.append(metrics);
    if (data.matches?.length) {
      fragment.append(section("Partidas da seleção", `${data.matches.length} jogos`, node("div", { class: "score-grid" }, data.matches.map(matchCard))));
    }
    if (data.shot_map?.length) {
      fragment.append(section("Mapa de finalizações", `${data.shot_map.length} chutes`, shotMap(data.shot_map), "wide-chart"));
      fragment.append(section("Fluxo de xG", teamName(team), xgFlowPlot(data.shot_map), "wide-chart"));
    }
    els.view.replaceChildren(fragment);
  }

  function renderDetail(data, page) {
    if (page === "matches") renderTheStatsApiMatch(data);
    else if (page === "players") renderPlayerDetail(data);
    else if (page === "teams") renderTeamDetail(data);
    else renderStandard(data, page);
  }

  function renderStandard(data, page) {
    const renderers = {
      overview: renderOverview,
      competition: renderCompetition,
      teams: renderTeams,
      players: renderPlayers,
      matches: renderMatches,
      shots: renderShots,
      thestatsapi_match: renderTheStatsApiMatch,
      "official-metrics": renderOfficialMetrics,
      availability: renderAvailability,
    };
    (renderers[page] || renderOverview)(data);
  }

  function renderHistory(data) {
    const editions = listFrom(data, ["editions", "history", "items", "data", "tournaments"]);
    const fragment = document.createDocumentFragment();
    fragment.append(pageHead("Arquivo · 1930—hoje", "Toda Copa deixa um rastro", "Explore a cobertura local por edição, com partidas, gols, seleções e campeãs conhecidas. Amostras avançadas podem ser parciais."));
    const metrics = metricGrid(data);
    if (metrics) fragment.append(metrics);
    if (!editions.length) {
      fragment.append(emptyState("O arquivo histórico ainda está vazio", "Quando as edições forem preparadas, elas aparecerão aqui sem serem confundidas com zeros."));
    } else {
      fragment.append(node("section", { class: "section" }, [
        node("div", { class: "section-heading" }, [node("h2", { text: "Edições no acervo" }), node("span", { text: `${editions.length} disponíveis` })]),
        node("div", { class: "timeline" }, editions.map((item, index) => {
          const row = flattenRow(item);
          const year = String(first(row, ["year", "edition", "edition_year"], "—"));
          const champion = first(row, ["champion", "winner", "campeao", "campea"], "Campeã não informada");
          return node("article", { class: "timeline-item" }, [
            node("span", { class: "year", text: year }),
            node("h3", { text: champion }),
            node("p", { text: editionCoverage(item) }),
            node("button", { type: "button", text: "Abrir edição", onclick: () => goTo(year, DEFAULT_PAGE) }),
          ]);
        })),
      ]));
    }
    els.view.replaceChildren(fragment);
  }

  function renderError(error) {
    if (error?.name === "AbortError") return;
    const card = node("section", { class: "state-card", role: "alert" }, [
      node("p", { class: "eyebrow", text: "Não foi possível carregar" }),
      node("h2", { text: "A conexão com os dados falhou" }),
      node("p", { text: "Tente novamente em instantes." }),
      node("button", { type: "button", text: "Tentar novamente", onclick: () => navigate(true) }),
    ]);
    els.view.replaceChildren(card);
  }

  async function loadCatalog() {
    const payload = await getJSON("/editions");
    state.editions = listFrom(payload, ["editions", "items", "data"]);
    if (!state.editions.length) throw new Error("O catálogo não retornou nenhuma edição.");
  }

  async function navigate(refresh = false) {
    const route = parseRoute();
    closeQuickView();
    closeStatPopover();
    state.pathname = location.pathname;
    state.controller?.abort();
    state.controller = new AbortController();
    state.year = route.year;
    state.page = route.page;
    state.detailId = route.detailId;
    state.matchPlayers = [];
    state.competitionData = null;
    setSkin(state.page, state.year);
    showLoading();
    els.menuButton.setAttribute("aria-expanded", "false");
    els.nav.classList.remove("is-open");
    try {
      if (!state.editions.length || refresh) await loadCatalog();
      renderCatalog();
      if (state.page !== "history") {
        const menus = editionMenus(state.edition || {});
        if (!menus.some(menu => menu.id === state.page)) {
          els.view.replaceChildren(emptyState("Visão indisponível nesta edição", "Escolha uma das áreas disponíveis no menu principal."));
          return;
        }
      }
      const path = state.detailId
        ? `/editions/${encodeURIComponent(state.year)}/${endpointFor[state.page]}/${encodeURIComponent(state.detailId)}`
        : `/editions/${encodeURIComponent(state.year)}/${endpointFor[state.page]}`;
      const data = state.page === "history"
        ? await getJSON("/history", { refresh })
        : await getJSON(path, { refresh });
      if (state.page === "history") renderHistory(data);
      else if (state.detailId) renderDetail(data, state.page);
      else renderStandard(data, state.page);
      document.title = `${state.page === "history" ? "Histórico" : menuLabels[state.page] || label(state.page)} · World Cup Analytics`;
      requestAnimationFrame(scrollToInternalAnchor);
    } catch (error) {
      renderError(error);
    } finally {
      els.view.setAttribute("aria-busy", "false");
    }
  }

  els.select.addEventListener("change", event => {
    const available = editionMenus(state.editions.find(item => editionYear(item) === event.target.value) || {});
    const page = available.some(menu => menu.id === state.page) ? state.page : DEFAULT_PAGE;
    goTo(event.target.value, page);
  });
  els.menuButton.addEventListener("click", () => {
    const open = !els.nav.classList.contains("is-open");
    els.nav.classList.toggle("is-open", open);
    els.menuButton.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", event => {
    const link = event.target.closest("a[href^='/']");
    if (!link || link.target || link.origin !== location.origin || link.pathname.startsWith("/api") || link.pathname.startsWith("/static")) return;
    event.preventDefault();
    history.pushState(null, "", link.pathname);
    navigate();
  });
  window.addEventListener("popstate", () => {
    if (state.pathname === location.pathname) scrollToInternalAnchor();
    else navigate();
  });
  window.addEventListener("hashchange", () => {
    if (location.hash.startsWith("#/")) {
      const route = parseRoute();
      goTo(route.year, route.page, route.detailId, { replace: true });
    } else scrollToInternalAnchor();
  });
  window.addEventListener("DOMContentLoaded", () => {
    if (location.hash.startsWith("#/")) {
      const route = parseRoute();
      goTo(route.year, route.page, route.detailId, { replace: true });
    } else if (location.pathname === "/") goTo(DEFAULT_YEAR, DEFAULT_PAGE, null, { replace: true });
    else navigate();
  });
})();
