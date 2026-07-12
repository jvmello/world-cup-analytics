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
    { id: "teams", label: "Seleções" },
    { id: "profile", label: "Perfil" },
  ];
  const menuAliases = {
    overview: "overview", inicio: "overview", home: "overview", visao_geral: "overview", competition: "competition",
    competicao: "competition", teams: "teams", times: "teams", paises: "teams",
    países: "teams", selecoes: "teams", seleções: "teams", players: "players",
    jogadores: "players", matches: "matches", partidas: "matches",
    profile: "profile", perfil: "profile",
    official_metrics: "official-metrics", "official-metrics": "official-metrics",
    estatisticas_oficiais: "official-metrics", shots: "shots", finalizacoes: "shots",
    thestatsapi_match: "thestatsapi_match", "thestatsapi-match": "thestatsapi_match",
    jogo_base: "thestatsapi_match", abertura: "thestatsapi_match",
    xg: "xg", availability: "availability", disponibilidade: "availability",
    history: "history", historico: "history",
  };
  const menuLabels = {
    overview: "Início", competition: "Competição", teams: "Seleções", profile: "Perfil",
    players: "Jogadores", matches: "Partidas", "official-metrics": "Métricas oficiais",
    thestatsapi_match: "Jogo base", shots: "Finalizações e xG", availability: "Disponibilidade",
  };
  const endpointFor = {
    overview: "overview", competition: "competition", teams: "teams", profile: "profiles",
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
    if (parts[0] === "about" || parts[0] === "sobre") {
      return { year: state.year || DEFAULT_YEAR, page: "about", detailId: null };
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
    if (page === "about") return "/about";
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
    // On the current edition the brand speaks for itself — the status line only shows on archive years.
    const coverageLine = els.coverage.closest(".coverage");
    if (coverageLine) coverageLine.hidden = state.year === DEFAULT_YEAR;
    els.coverage.textContent = state.year === DEFAULT_YEAR
      ? ""
      : `Arquivo da Copa do Mundo ${state.year} · ${coverage}`;
    els.footerSource.replaceChildren(node("span", { text: "Créditos, fontes e metodologia na página " }), node("a", { href: "/about", text: "Sobre" }), node("span", { text: "." }));
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
      class: "nav-link mobile-history-link", href: "/about", text: "Sobre",
      ...(state.page === "about" ? { "aria-current": "page" } : {}),
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
      node("article", { class: "metric", "data-design-component": "metric-card", title: metricTitle(key) }, [
        node("span", { class: "metric-label", text: metricName(key), title: metricTitle(key), "data-tooltip": metricFormula(key) || null }),
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
  const METRIC_FORMULAS = {
    goals_per_match: "Gols por jogo = gols / partidas",
    goals_per_game: "Gols por jogo = gols / jogos",
    goals_per_90: "Gols por 90 = gols / minutos * 90",
    assists_per_90: "Assistências por 90 = assistências / minutos * 90",
    xg_per_game: "xG por jogo = xG / jogos",
    xg_per_90: "xG por 90 = xG / minutos * 90",
    xa_per_90: "xA por 90 = xA / minutos * 90",
    xg_per_shot: "xG por finalização = xG / finalizações",
    goals_minus_xg: "Gols − xG = gols marcados − gols esperados",
    xg_difference: "Saldo de xG = xG criado − xG cedido",
    xga_per_game: "xG cedido por jogo = xG cedido / jogos",
    shots_per_game: "Finalizações por jogo = finalizações / jogos",
    shots_per_90: "Finalizações por 90 = finalizações / minutos * 90",
    shots_against_per_game: "Finalizações sofridas por jogo = finalizações sofridas / jogos",
    shot_conversion: "Conversão = gols / finalizações",
    conversion: "Conversão = gols / finalizações",
    shot_accuracy: "Precisão dos chutes = chutes no alvo / finalizações",
    pass_accuracy: "Precisão de passe = passes certos / passes",
    defensive_actions_per_90: "Ações defensivas por 90 = ações defensivas / minutos * 90",
    recoveries_per_game: "Recuperações por jogo = recuperações / jogos",
    tackles_per_game: "Desarmes por jogo = desarmes / jogos",
    goals_against_per_game: "Gols sofridos por jogo = gols sofridos / jogos",
  };
  const RANKING_SCOPE_BY_METRIC = {
    goals_per_match: "por jogo", goals_per_game: "por jogo", goals_per_90: "por 90",
    assists_per_90: "por 90", xg_per_game: "por jogo", xg_per_90: "por 90",
    xa_per_90: "por 90", shots_per_game: "por jogo", shots_per_90: "por 90",
    xga_per_game: "por jogo", shots_against_per_game: "por jogo",
    recoveries_per_game: "por jogo", tackles_per_game: "por jogo",
    defensive_actions_per_90: "por 90", conversion: "percentual",
    shot_conversion: "percentual", shot_accuracy: "percentual",
    pass_accuracy: "percentual", xg_per_shot: "média por finalização",
  };
  const metricFormula = key => METRIC_FORMULAS[key] || null;
  const rankingScope = key => RANKING_SCOPE_BY_METRIC[key] || (/_per_90$/.test(key) ? "por 90" : /_per_game$/.test(key) ? "por jogo" : /percentage|accuracy|conversion/.test(key) ? "percentual" : "total");
  const metricTitle = key => {
    const formula = metricFormula(key);
    return formula ? `${metricName(key)} · ${formula}` : metricName(key);
  };
  const EVENT_LABELS = {
    goal: "Gol",
    own_goal: "Gol contra",
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
    shot_post: "Na trave",
  };
  const EVENT_ICONS = {
    goal: "●", own_goal: "●", penalty: "●", shot_on_target: "◎", shot_off_target: "○",
    shot_blocked: "×", foul: "!", yellow_card: "■", red_card: "■",
    substitution: "⇄", corner_kick: "⚑", offside: "↥", var: "◇",
    added_time: "+", period_start: "▶", period_end: "■", shot_post: "▲",
  };
  const NARRATIVE_EVENT_TYPES = new Set([
    "goal", "own_goal", "penalty", "var", "red_card", "yellow_card", "substitution", "shot_on_target",
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
    d: "DEF", df: "DEF", def: "DEF", defender: "DEF", defesa: "DEF", defensor: "DEF", zagueiro: "DEF", lateral: "DEF", ala: "DEF",
    lateral_direito: "DEF", lateral_esquerdo: "DEF", ala_direito: "DEF", ala_esquerdo: "DEF",
    m: "MEI", mf: "MEI", mei: "MEI", midfielder: "MEI", meio: "MEI", meio_campo: "MEI", volante: "MEI",
    meio_campista_central: "MEI", meia_ofensivo: "MEI", meia_lateral_direito: "MEI", meia_lateral_esquerdo: "MEI",
    f: "ATA", fw: "ATA", ata: "ATA", forward: "ATA", atacante: "ATA", ponta: "ATA", centroavante: "ATA",
    ponta_direita: "ATA", ponta_esquerda: "ATA", segundo_atacante: "ATA",
  };

  function positionLabel(value) {
    if (!value) return "—";
    const normalized = String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim().replace(/[\s-]+/g, "_");
    if (POSITION_CODES[normalized]) return POSITION_CODES[normalized];
    const prefix = Object.keys(POSITION_CODES).find(key => normalized.startsWith(`${key}_`) || normalized.endsWith(`_${key}`));
    return prefix ? POSITION_CODES[prefix] : "—";
  }

  function resolvedPlayerPosition(player, compact = false) {
    const raw = player?.resolved_position || player?.primary_inferred_role || player?.api_position_group || player?.position;
    const full = { G: "Goleiro", GK: "Goleiro", D: "Defensor", DF: "Defensor", M: "Meio-campista", MF: "Meio-campista", F: "Atacante", FW: "Atacante" }[String(raw || "").toUpperCase()] || raw || "Posição não informada";
    return compact ? positionLabel(full) : String(full);
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
    const sourceName = typeof team === "string" ? team : first(team, ["api_team_name", "team_name", "name"], name);
    const code = teamCode(sourceName);
    const translated = displayTeamName(name);
    if (availableFlagCodes.has(code)) {
      return node("img", { class: className, src: `/static/flags/${code}.svg`, alt: `Bandeira de ${translated}`, loading: "lazy" });
    }
    return node("span", { class: `${className} flag-fallback`, text: code.toUpperCase(), "aria-label": `Bandeira indisponível: ${translated}` });
  }

  function flagAssetSource(team) {
    const customPath = typeof team === "object" ? team?.flag_asset_path : null;
    if (customPath) return `/static/${String(customPath).replace(/^\/?static\//, "")}`;
    const sourceName = typeof team === "string" ? team : first(team, ["api_team_name", "team_name", "name"], rawTeamName(team));
    const code = teamCode(sourceName);
    return availableFlagCodes.has(code) ? `/static/flags/${code}.svg` : null;
  }

  function playerPhotoSource(player) {
    if (player?.photo_asset_path) return `/static/${String(player.photo_asset_path).replace(/^\/?static\//, "")}`;
    return player?.photo_url || null;
  }

  function playerPhotoNode(player) {
    const name = personName(player);
    const initials = name.split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase() || "?";
    const fallback = node("span", { text: initials, "aria-hidden": "true" });
    const wrapper = node("span", { class: "player-profile-photo", "aria-label": `Foto de ${name}` }, fallback);
    const source = player?.photo_asset_path
      ? `/static/${String(player.photo_asset_path).replace(/^\/?static\//, "")}`
      : player?.photo_url;
    if (source) {
      const image = node("img", { src: source, alt: player.photo_alt_text || `Foto de ${name}`, loading: "lazy" });
      image.onerror = () => image.remove();
      wrapper.append(image);
    }
    return wrapper;
  }

  function teamLabel(team, className = "team-label") {
    const name = typeof team === "string" ? team : rawTeamName(team);
    return node("span", { class: className, title: displayTeamName(name) }, [
      flagNode(team),
      node("span", { text: displayTeamName(name) }),
    ]);
  }

  function teamColor(team, fallbackIndex = 0) {
    return teamColors[teamCode(team)] || ["#66ffd7", "#ff3c1f", "#c8ff1d", "#2167ff"][fallbackIndex % 4];
  }

  // Kit da partida (cores de camisa designadas pela FIFA) quando o payload traz
  // home_kit/away_kit; fora disso, cai nas cores fixas de identidade.
  function impactMaxNote(player) {
    if (number(player?.impact_score) === null || number(player.impact_score) < 99.5) return null;
    const reasons = [
      number(player.goals) > 0 ? `${formatValue(player.goals)} ${number(player.goals) === 1 ? "gol" : "gols"}` : null,
      number(player.assists) > 0 ? `${formatValue(player.assists)} assist.` : null,
      number(player.xg) > 0 ? `${formatValue(player.xg)} xG` : null,
      number(player.saves) > 0 ? `${formatValue(player.saves)} defesas` : null,
    ].filter(Boolean).slice(0, 3);
    return node("small", { class: "impact-max-note", text: `Teto da partida — nota relativa ao melhor desempenho do jogo${reasons.length ? `: ${reasons.join(", ")}` : ""}.` });
  }

  function penaltyVerdict(match) {
    const home = number(match?.penalty_home_score), away = number(match?.penalty_away_score);
    if (home === null || away === null || home === away) return "Decidido nos pênaltis";
    const winner = displayTeamName(home > away ? match.home_team : match.away_team);
    return `${winner} venceu nos pênaltis por ${formatValue(Math.max(home, away))}–${formatValue(Math.min(home, away))}`;
  }

  function matchKits(match) {
    if (!match) return null;
    const kits = {};
    if (match.home_kit && match.home_team) kits[match.home_team] = match.home_kit;
    if (match.away_kit && match.away_team) kits[match.away_team] = match.away_kit;
    return Object.keys(kits).length ? kits : null;
  }

  function kitColor(kits, name, fallbackIndex = 0) {
    const kit = kits?.[name];
    return kit?.display_hex || kit?.hex || teamColor(name, fallbackIndex);
  }

  function matchPalette(home, away, kits = null) {
    return `--home-color:${kitColor(kits, home, 0)};--away-color:${kitColor(kits, away, 1)};`;
  }

  function formatMatchDate(value) {
    if (!value) return "Data não informada";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Data não informada";
    const dayMonthYear = new Intl.DateTimeFormat("pt-BR", {
      timeZone: "America/Sao_Paulo", day: "2-digit", month: "short", year: "numeric",
    }).format(date).replace(/ de /g, " ").replace(/\./g, "");
    const time = new Intl.DateTimeFormat("pt-BR", {
      timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit",
    }).format(date);
    return `${dayMonthYear}, ${time}`;
  }

  function minuteLabel(goal) {
    return `${formatValue(goal.minute)}${goal.extra_time ? `+${goal.extra_time}` : ""}'`;
  }

  function section(title, meta, content, className = "", id = null) {
    return node("section", { class: `section ${className}`.trim(), id }, [
      node("div", { class: "section-heading" }, [
        node("h2", { text: title }),
        meta ? (meta instanceof Node ? meta : node("span", { text: meta })) : null,
      ]),
      content,
    ]);
  }

  function kpis(summary, keys = Object.keys(summary || {})) {
    const values = keys.filter(key => summary?.[key] !== undefined && summary[key] !== null);
    if (!values.length) return null;
    return node("div", { class: "metric-grid" }, values.map(key =>
      node("article", { class: "metric", "data-design-component": "metric-card", title: metricTitle(key) }, [
        node("span", { class: "metric-label", text: metricName(key), title: metricTitle(key), "data-tooltip": metricFormula(key) || null }),
        node("strong", { class: "metric-value", text: formatValue(summary[key]) }),
      ])
    ));
  }

  const PIE_SLICE_COLORS = [
    "var(--wc26-teal, #4fbfa6)", "var(--wc26-blue, #5578bd)", "var(--wc26-green, #8fbd46)",
    "var(--wc26-yellow, #d4b84c)", "var(--wc26-red, #c94f4a)", "var(--wc26-orange, #c77a43)",
    "var(--wc26-purple, #7965a8)",
  ];

  function pieChart(rows, valueKey, { name = item => item.label, unit = "" } = {}) {
    const clean = rows
      .map(item => ({ item, value: Math.max(0, number(item?.[valueKey]) || 0) }))
      .filter(({ value }) => value > 0);
    const total = clean.reduce((sum, { value }) => sum + value, 0);
    if (!total) return emptyState(`Sem dados para ${metricName(valueKey)}`, "Esta métrica não está disponível no recorte selecionado.");
    const size = 200, radius = 92, center = size / 2;
    const svg = svgNode("svg", { viewBox: `0 0 ${size} ${size}`, role: "img", "aria-label": `Distribuição de ${metricName(valueKey)}` });
    let angle = -Math.PI / 2;
    clean.forEach(({ item, value }, index) => {
      const fraction = value / total;
      const nextAngle = angle + fraction * 2 * Math.PI;
      const x1 = center + radius * Math.cos(angle), y1 = center + radius * Math.sin(angle);
      const x2 = center + radius * Math.cos(nextAngle), y2 = center + radius * Math.sin(nextAngle);
      const largeArc = fraction > 0.5 ? 1 : 0;
      const path = fraction >= 0.999
        ? `M ${center} ${center - radius} A ${radius} ${radius} 0 1 1 ${center - 0.01} ${center - radius} Z`
        : `M ${center} ${center} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`;
      const percentage = fraction * 100;
      const tooltip = `${name(item)} · ${formatValue(value)}${unit} · ${formatValue(percentage)}%`;
      const slice = svgNode("path", {
        d: path, class: "pie-slice", style: `--slice-color:${PIE_SLICE_COLORS[index % PIE_SLICE_COLORS.length]}`,
        tabindex: "0", role: "img", "aria-label": tooltip,
      });
      svg.append(attachChartTooltip(slice, tooltip));
      angle = nextAngle;
    });
    const legend = node("ul", { class: "pie-legend" }, clean.map(({ item, value }, index) => node("li", {}, [
      node("i", { style: `--slice-color:${PIE_SLICE_COLORS[index % PIE_SLICE_COLORS.length]}`, "aria-hidden": "true" }),
      node("span", { text: name(item) }),
      node("b", { text: `${formatValue(value)}${unit}` }),
    ])));
    return node("div", { class: "pie-chart-wrap" }, [node("div", { class: "pie-chart-svg" }, svg), legend]);
  }

  function horizontalBars(rows, metric, { name = personName, limit = 10, unit = "" } = {}) {
    const clean = rows
      .map(item => ({ item, value: number(item?.[metric]) }))
      .filter(item => item.value !== null)
      .slice(0, limit);
    if (!clean.length) return emptyState(`Sem dados para ${metricName(metric)}`, "Esta métrica não está disponível no recorte selecionado.");
    const max = Math.max(...clean.map(item => Math.abs(item.value)), 1);
    const scope = rankingScope(metric);
    return node("ol", { class: "bar-chart", "data-ranking-scope": scope, "aria-label": `Ranking de ${metricName(metric)} (${scope})` }, clean.map(({ item, value }, index) => {
      const formula = metricFormula(metric);
      const tooltip = `${metricName(metric)} (${scope}) · ${name(item)}: ${formatValue(value)}${unit}${formula ? ` · Fórmula: ${formula}` : ""}`;
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

  function scorePill(homeValue, awayValue, { size = "md", homeName = "", awayName = "" } = {}) {
    return node("span", {
      class: `score-pill score-pill-${size}`,
      "aria-label": `${homeName ? `${displayTeamName(homeName)} ` : ""}${formatValue(homeValue)}, ${awayName ? `${displayTeamName(awayName)} ` : ""}${formatValue(awayValue)}`,
    }, [
      node("strong", { text: formatValue(homeValue) }),
      node("span", { class: "score-pill-sep", "aria-hidden": "true", text: ":" }),
      node("strong", { text: formatValue(awayValue) }),
    ]);
  }

  function scoreText(homeValue, awayValue, { homeName = "", awayName = "" } = {}) {
    return node("strong", {
      class: "score-text",
      "aria-label": `${homeName ? `${displayTeamName(homeName)} ` : ""}${formatValue(homeValue)}, ${awayName ? `${displayTeamName(awayName)} ` : ""}${formatValue(awayValue)}`,
      text: `${formatValue(homeValue)}–${formatValue(awayValue)}`,
    });
  }

  function scoreCard(match, { hero = false } = {}) {
    const home = first(match, ["home_team"], "Mandante");
    const away = first(match, ["away_team"], "Visitante");
    // ?? instead of first(): knockout matches carry group_name: null, which must not
    // swallow the valid stage right after it.
    const stage = match?.competition_stage ?? match?.group_name ?? match?.stage ?? "Partida";
    const stageLabel = /^[A-Z]$/i.test(String(stage)) ? `Grupo ${stage}` : matchStageLabel(stage);
    const date = first(match, ["match_date", "date"], null);
    const goals = Array.isArray(match?.goals) ? match.goals : [];
    const stadium = first(match, ["stadium", "venue"], null);
    const venueCity = first(match, ["venue_city"], null);
    const stadiumLabel = stadium && venueCity ? `${stadium} · ${venueCity}` : stadium;
    const referee = first(match, ["referee", "main_referee"], null);
    const penalties = metricAvailable(match?.penalty_home_score) && metricAvailable(match?.penalty_away_score);
    const status = penalties ? "Pênaltis" : match?.went_to_extra_time ? "Prorrogação" : competitionMatchStatus(match);
    const hasScore = metricAvailable(match?.home_score) && metricAvailable(match?.away_score);
    const teamSurface = (name, id) => id
      ? node("button", { type: "button", class: "score-team-link", onclick: () => goToProfile("team", id) }, teamLabel(name))
      : teamLabel(name);
    const detailRows = [
      !hero ? ["Data", formatMatchDate(date)] : null,
      stadiumLabel ? ["Estádio", stadiumLabel] : null,
      referee ? ["Árbitro", referee] : null,
    ].filter(Boolean);
    return node("article", { class: `score-card${hero ? " match-score-card" : ""}`, style: matchPalette(home, away, matchKits(match)) }, [
      node("div", { class: "score-meta" }, [
        node("span", {}, [node("strong", { text: stageLabel }), node("em", { class: `match-status is-${status.toLowerCase().replace(/\s+/g, "-")}`, text: status })]),
        node("time", { dateTime: date || "", text: formatMatchDate(date).replace(", ", " · ") }),
      ]),
      node("div", { class: "score-line" }, [
        node("strong", {}, teamSurface(home, match?.home_team_id)),
        hasScore
          ? (hero
              ? scorePill(match?.home_score, match?.away_score, { size: "lg", homeName: home, awayName: away })
              : scoreText(match?.home_score, match?.away_score, { homeName: home, awayName: away }))
          : node("span", { class: "score-pending", text: "×" }),
        node("strong", {}, teamSurface(away, match?.away_team_id)),
      ]),
      penalties ? node("p", { class: "score-penalties is-verdict", text: penaltyVerdict(match) }) : null,
      hero && match?.stage && !match?.group_name ? node("button", { type: "button", class: "action-link score-bracket-cta", text: "Ver chaveamento →", onclick: () => goTo(state.year, "competition") }) : null,
      goals.length ? node("ol", { class: "score-goals", "aria-label": "Gols da partida" }, goals.map(goal => node("li", {
        class: goal.team_name === away ? "away" : "home",
      }, [
        node("span", { class: "goal-minute", text: minuteLabel(goal) }),
        node("span", { text: goal.is_own_goal ? `${personName(goal)} (contra)` : personName(goal) }),
      ]))) : null,
      node("dl", { class: `score-details${hero ? " score-details-compact" : ""}` }, detailRows.map(([key, value]) =>
        node("div", {}, [node("dt", { text: key }), node("dd", { text: value })])
      )),
    ]);
  }

  function routeTo(page, id) {
    if (!id) return;
    goTo(state.year, page, id);
  }

  function goToProfile(kind, id = null) {
    const params = new URLSearchParams({ type: kind });
    if (id) params.set("id", id);
    history.pushState(null, "", `${routePath(state.year, "profile")}?${params}`);
    navigate();
  }

  function goToCompare(kind, aId = null, bId = null) {
    const params = new URLSearchParams({ type: "compare", kind });
    if (aId) params.set("a", aId);
    if (bId) params.set("b", bId);
    history.pushState(null, "", `${routePath(state.year, "profile")}?${params}`);
    navigate();
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
      if (event.key === "Enter") {
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

  function attachTabListKeyNav(tablist) {
    tablist.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      const tabs = [...tablist.querySelectorAll('[role="tab"]')].filter(tab => !tab.disabled);
      if (!tabs.length) return;
      const currentIndex = tabs.indexOf(document.activeElement);
      let nextIndex;
      if (event.key === "Home") nextIndex = 0;
      else if (event.key === "End") nextIndex = tabs.length - 1;
      else if (event.key === "ArrowRight") nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % tabs.length;
      else nextIndex = currentIndex < 0 ? 0 : (currentIndex - 1 + tabs.length) % tabs.length;
      event.preventDefault();
      tabs[nextIndex].focus();
      tabs[nextIndex].click();
    });
    return tablist;
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

  function scatterEntityMarker(item, { cx, cy, kind, selected = false, tooltip, onSelect = null, dense = false, plain = false }) {
    const isPlayer = kind === "player";
    // Modo plain: a massa vira ponto simples; bandeira/foto ficam para o
    // selecionado e para os destaques — o scatter continua legível com 300+.
    if (plain && !selected) {
      const dot = svgNode("circle", {
        cx, cy, r: 3.4,
        class: `scatter-plain-dot is-${kind}`,
        style: `--team-color:${teamColor(item?.team_name, 0)}`,
        tabindex: "0", role: onSelect ? "button" : "img", "aria-label": tooltip,
      });
      if (onSelect) {
        dot.addEventListener("click", () => onSelect(item));
        dot.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(item); }
        });
      }
      return attachChartTooltip(dot, tooltip);
    }
    const flagSource = flagAssetSource(item);
    const photoSource = isPlayer ? playerPhotoSource(item) : null;
    const imageSource = photoSource || flagSource;
    const group = svgNode("g", {
      transform: `translate(${cx} ${cy})`,
      class: `scatter-entity-marker is-${kind}${selected ? " is-selected" : ""}${dense && !selected ? " is-dense" : ""}`,
      tabindex: "0", role: "button", "aria-pressed": String(selected), "aria-label": tooltip,
    });
    group.append(svgNode("circle", { cx: 0, cy: 0, r: 12, class: "scatter-marker-hitbox" }));
    if (imageSource) {
      const usesPhoto = Boolean(photoSource);
      group.append(usesPhoto
        ? svgNode("circle", { cx: 0, cy: 0, r: 10, class: "scatter-marker-frame is-photo" })
        : svgNode("rect", { x: -12, y: -8.5, width: 24, height: 17, rx: 2.5, class: "scatter-marker-frame is-flag" }));
      const image = svgNode("image", {
        href: imageSource,
        x: usesPhoto ? -9 : -11,
        y: usesPhoto ? -9 : -7.5,
        width: usesPhoto ? 18 : 22,
        height: usesPhoto ? 18 : 15,
        preserveAspectRatio: "xMidYMid slice",
        class: `scatter-marker-image ${usesPhoto ? "is-photo" : "is-flag"}`,
      });
      if (usesPhoto && flagSource) image.addEventListener("error", () => {
        image.setAttribute("href", flagSource);
        image.setAttribute("x", "-11"); image.setAttribute("y", "-7.5");
        image.setAttribute("width", "22"); image.setAttribute("height", "15");
        image.setAttribute("class", "scatter-marker-image is-flag");
      }, { once: true });
      group.append(image);
    } else {
      const fallback = isPlayer ? personName(item) : teamName(item);
      group.append(svgNode("text", { x: 0, y: 3, class: "scatter-marker-fallback", "text-anchor": "middle" }, fallback.slice(0, 2).toUpperCase()));
    }
    if (onSelect) {
      group.addEventListener("click", () => onSelect(item));
      group.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(item); }
      });
    }
    return attachChartTooltip(group, tooltip);
  }

  const SHOT_OUTCOME_LABELS = {
    goal: "Gol", save: "Defendido", saved: "Defendido", miss: "Para fora",
    off_target: "Para fora", block: "Bloqueado", blocked: "Bloqueado", post: "Na trave",
  };
  // Sources disagree on the separator: TheStatsAPI uses underscores (left_foot, set_piece),
  // StatsBomb uses spaces ("Left Foot", "Open Play") — the keys cover all three forms.
  const BODY_PART_LABELS = {
    "right-foot": "Pé direito", "right_foot": "Pé direito", "right foot": "Pé direito",
    "left-foot": "Pé esquerdo", "left_foot": "Pé esquerdo", "left foot": "Pé esquerdo",
    head: "Cabeça", other: "Outra parte",
  };
  const SHOT_TYPE_LABELS = {
    assisted: "Jogada assistida", "open-play": "Bola rolando", "open play": "Bola rolando", corner: "Escanteio",
    regular: "Bola rolando", "set-piece": "Bola parada", "set_piece": "Bola parada", "set piece": "Bola parada",
    "fast-break": "Contra-ataque", "fast_break": "Contra-ataque", "fast break": "Contra-ataque",
    "throw-in-set-piece": "Lateral ensaiado", "throw_in_set_piece": "Lateral ensaiado",
    "free-kick": "Falta", "free_kick": "Falta", "free kick": "Falta",
    penalty: "Pênalti", shootout: "Disputa de pênaltis", rebound: "Rebote",
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

  // 120×80 pitch with markings in real proportion (105×68 m): penalty box 16.5 m deep
  // × 40.32 m wide, six-yard box 5.5 × 18.32 m, penalty spot at 11 m.
  const PITCH = (() => {
    const xAt = pct => 1 + pct * 1.18;
    const yAt = pct => 1 + pct * 0.78;
    const length = 105, width = 68;
    const boxX = xAt(16.5 / length * 100), sixX = xAt(5.5 / length * 100), spotX = xAt(11 / length * 100);
    const boxHalf = 40.32 / width * 50, sixHalf = 18.32 / width * 50;
    const boxY = yAt(50 - boxHalf), boxHeight = yAt(50 + boxHalf) - boxY;
    const sixY = yAt(50 - sixHalf), sixHeight = yAt(50 + sixHalf) - sixY;
    return {
      xAt, yAt, spotX,
      markings: [
        ["line", { x1: 60, y1: 1, x2: 60, y2: 79 }],
        ["circle", { cx: 60, cy: 40, r: 9.15 / length * 118 }],
        ["rect", { x: 1, y: boxY, width: boxX - 1, height: boxHeight }],
        ["rect", { x: 120 - boxX, y: boxY, width: boxX - 1, height: boxHeight }],
        ["rect", { x: 1, y: sixY, width: sixX - 1, height: sixHeight }],
        ["rect", { x: 120 - sixX, y: sixY, width: sixX - 1, height: sixHeight }],
        ["circle", { cx: spotX, cy: 40, r: 0.7 }],
        ["circle", { cx: 120 - spotX, cy: 40, r: 0.7 }],
        ["rect", { x: 1, y: 1, width: 118, height: 78 }],
      ],
    };
  })();

  const PENALTY_SHOT_TYPES = new Set(["penalty", "shootout"]);

  function isPenaltyShot(item) {
    return Boolean(item?.is_penalty) || PENALTY_SHOT_TYPES.has(String(item?.shot_type || "").toLowerCase());
  }

  // TheStatsAPI publishes coordinates in % (x = distance from the attacked goal along the
  // length, y = position across the width); its rows carry the `xg`/`is_penalty` keys.
  // Archive editions (StatsBomb) already arrive in the 120×80 space and lack those keys.
  const shotUsesPercentUnits = item => item?.xg !== undefined || item?.is_penalty !== undefined;

  function shotMatchLabel(shot) {
    const home = displayTeamName(shot?.home_team);
    const away = displayTeamName(shot?.away_team);
    if (!shot?.home_team && !shot?.away_team) return "Partida não informada";
    const homeScore = metricAvailable(shot?.home_score) ? formatValue(shot.home_score) : "";
    const awayScore = metricAvailable(shot?.away_score) ? formatValue(shot.away_score) : "";
    const score = homeScore !== "" && awayScore !== "" ? ` ${homeScore}–${awayScore} ` : " × ";
    return `${home}${score}${away}`;
  }

  function shotOpponentName(shot) {
    const team = shot?.team_name;
    if (team && shot?.home_team === team) return displayTeamName(shot.away_team);
    if (team && shot?.away_team === team) return displayTeamName(shot.home_team);
    return "Adversário não informado";
  }

  function shotMap(rows, { selectedKey = null, onSelect = null, compactMarkers = false, kits = null } = {}) {
    const home = first(rows[0] || {}, ["home_team"], null);
    const away = first(rows[0] || {}, ["away_team"], null);
    const shots = rows.map(item => {
      const rawX = number(item?.x);
      const rawY = number(item?.y);
      const isAway = away && item?.team_name === away;
      const teamIndex = isAway ? 1 : 0;
      if (rawX === null || rawY === null) return null;
      let x, y;
      if (isPenaltyShot(item)) {
        // In-game penalties always sit on the spot; shootout kicks never reach this
        // map — they live in the dedicated penalty section.
        x = PITCH.spotX;
        y = 40;
      } else if (shotUsesPercentUnits(item)) {
        // The provider's y axis runs opposite to the broadcast view (verified against
        // TV footage), so mirror it. The cropped profile map already matches this
        // orientation — its cx = y equals this flip after the 90° attack-up rotation.
        x = PITCH.xAt(rawX);
        y = PITCH.yAt(100 - rawY);
      } else {
        x = rawX;
        y = rawY;
      }
      // Away side mirrored with a 180° rotation (x and y), preserving which side of the
      // pitch the play happened on relative to the attacking direction.
      return { item, x: isAway ? 120 - x : x, y: isAway ? 80 - y : y, teamIndex };
    }).filter(Boolean);
    if (!shots.length) return emptyState("Mapa de chutes indisponível", "Não há coordenadas de finalização para esta edição.");
    const svg = svgNode("svg", {
      viewBox: "0 0 120 80",
      class: "pitch-svg",
      role: "img",
      "aria-label": `Campo com ${shots.length} finalizações`,
      style: matchPalette(home, away, kits),
    });
    svg.append(svgNode("title", {}, "Mapa de finalizações. Gols aparecem em destaque."));
    for (let band = 0; band < 10; band += 1) {
      svg.append(svgNode("rect", { x: 1 + band * 11.8, y: 1, width: 11.8, height: 78, class: `pitch-stripe${band % 2 ? " is-alt" : ""}` }));
    }
    PITCH.markings.forEach(([tag, attrs]) => svg.append(svgNode(tag, { ...attrs, class: "pitch-line" })));
    shots.forEach(({ item, x, y, teamIndex }) => {
      const goal = Boolean(item?.is_goal) || String(item?.shot_outcome).toLowerCase() === "goal";
      const cx = Math.max(1, Math.min(119, x));
      const cy = Math.max(1, Math.min(79, y));
      const xg = Math.max(0, number(item?.statsbomb_xg ?? item?.xg) || 0);
      const size = compactMarkers ? Math.max(.8, Math.min(2.2, .8 + xg * 2.6)) : Math.max(1, Math.min(3.1, 1 + xg * 4));
      const key = shotKey(item);
      const selected = selectedKey === key;
      const marker = goal
        ? svgNode("polygon", {
          points: starPoints(cx, cy, size * (compactMarkers ? 1.1 : 1), 0.22),
          class: `shot-point team-${teamIndex} is-goal${selected ? " is-selected" : ""}`,
          style: `--team-color:${kitColor(kits, item?.team_name, teamIndex)}`,
          tabindex: "0",
          "aria-label": `${personName(item)}, ${teamName(item)}, gol, xG ${formatValue(item?.statsbomb_xg)}`,
          ...(onSelect ? { "aria-pressed": String(selected), role: "button" } : { role: "img" }),
        })
        : svgNode("circle", {
          cx,
          cy,
          r: size,
          class: `shot-point team-${teamIndex}${selected ? " is-selected" : ""}`,
          style: `--team-color:${kitColor(kits, item?.team_name, teamIndex)}`,
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
      const outcome = SHOT_OUTCOME_LABELS[String(item?.shot_outcome || "").toLowerCase()] || (goal ? "Gol" : "Finalização");
      const bodyPart = BODY_PART_LABELS[String(item?.body_part || "").toLowerCase()] || "Parte do corpo não informada";
      const shotType = SHOT_TYPE_LABELS[String(item?.shot_type || "").toLowerCase()] || "Situação não informada";
      const tooltip = `${formatValue(item?.minute)}' · ${personName(item)} · ${teamName(item)} · ${outcome} · xG ${formatValue(xg)} · ${bodyPart} · ${shotType}`;
      svg.append(attachChartTooltip(marker, tooltip));
    });
    return node("div", { class: "pitch-wrap" }, [
      svg,
      node("div", { class: "chart-legend" }, [
        home ? node("span", {}, [node("i", { class: "legend-dot", style: `--team-color:${kitColor(kits, home, 0)}` }), displayTeamName(home)]) : null,
        away ? node("span", {}, [node("i", { class: "legend-dot", style: `--team-color:${kitColor(kits, away, 1)}` }), displayTeamName(away)]) : null,
        node("span", { class: "shot-symbol-legend", text: "Círculo = chute · Estrela = gol · Tamanho = xG · Cor = seleção" }),
      ]),
    ]);
  }

  function xgFlowPlot(rows, kits = null) {
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
      const color = kitColor(kits, team, teamIndex);
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
            points: starPoints(cx, cy, 6, 0.22),
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
        if (point.item.is_goal) {
          svg.append(svgNode("text", {
            x: cx + 8,
            y: cy - 8,
            class: "xg-goal-label",
          }, `${formatValue(point.minute)}' ${point.item.player_name || "Gol"}`));
        }
      });
    });
    return node("div", { class: "svg-chart" }, [
      svg,
      node("div", { class: "chart-legend xg-total-legend" }, teams.map((team, index) => {
        const total = clean.filter(point => point.team === team).at(-1)?.value;
        return node("span", {}, [
          node("i", { class: `legend-line team-${index % 2}`, style: `--team-color:${kitColor(kits, team, index)}` }),
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
    const fragment = document.createDocumentFragment();
    const message = first(data, ["notice", "message", "coverage_message", "warning"]);
    if (message && !technicalTextPattern.test(message)) fragment.append(node("aside", { class: "notice", text: message }));
    const summary = homeSummaryStrip(data.summary || {});
    if (summary) fragment.append(summary);

    const pulse = homePulse(data.pulse || {});
    if (pulse) fragment.append(section("Pulso da Copa", null, pulse, "home-pulse-section"));

    const bracket = homeBracketSummary(data.knockout_summary || {});
    if (bracket) fragment.append(section("Caminho do mata-mata", null, bracket, "home-bracket-section"));

    const leaders = data.leaders || {};
    const highlights = homeHighlights(data.highlights || {}, leaders);
    if (highlights) fragment.append(section("Destaques da Copa", null, highlights, "home-highlights-section"));

    // Two distinct editorial blocks: individual leaders (3 cards) and team
    // leaderboards (4 cards) — players and teams never share a grid.
    const buildPanels = definitions => definitions
      .filter(([, , rows]) => rows?.length)
      .map(([kicker, title, rows, metric, entity]) => homeRankingPanel({ kicker, title, rows, metric, entity }));
    const leaderPanels = buildPanels([
      ["Jogadores", "Gols", leaders.players?.goals, "goals", "player"],
      ["Jogadores", "xG", leaders.players?.xg, "xg", "player"],
      ["Jogadores", "Assistências", leaders.players?.assists, "assists", "player"],
    ]);
    if (leaderPanels.length) fragment.append(section("Líderes da Copa", null, node("div", { class: "home-ranking-grid is-players" }, leaderPanels), "home-leaders-section"));
    const teamPanels = buildPanels([
      ["Seleções", "Maior xG", leaders.teams?.xg, "xg", "team"],
      ["Seleções", "Melhor saldo de xG", leaders.teams?.xg_difference, "xg_difference", "team"],
      ["Seleções", "Mais gols", leaders.teams?.goals_for, "goals_for", "team"],
      // team_leaders ordena tudo do maior para o menor; para "menor xG cedido"
      // basta inverter a lista completa.
      ["Seleções", "Menor xG cedido", leaders.teams?.xga ? [...leaders.teams.xga].reverse() : null, "xga", "team"],
    ]);
    if (teamPanels.length) fragment.append(section("Seleções em destaque", null, node("div", { class: "home-ranking-grid is-teams" }, teamPanels), "home-leaders-section home-team-leaders-section"));

    const explorer = homeDiscoveryLab(data.discoveries || {});
    if (explorer) fragment.append(section("Explorar estatísticas", null, explorer, "home-explore-section"));
    if (!summary && !leaderPanels.length) fragment.append(emptyState());
    els.view.replaceChildren(fragment);
  }

  function homeCompetitionProgress(summary) {
    const finished = number(summary.finished), total = number(summary.matches);
    if (finished === null || total === null || total <= 0) return null;
    const percent = Math.max(0, Math.min(100, finished / total * 100));
    const percentLabel = `${formatValue(Math.round(percent))}%`;
    return node("div", { class: "home-competition-progress", role: "img", "aria-label": `${percentLabel} da competição concluída: ${formatValue(finished)} de ${formatValue(total)} jogos disputados.` }, [
      node("div", { class: "home-progress-meta" }, [
        node("span", { text: `${percentLabel} da competição concluída` }),
        node("small", { text: `${formatValue(finished)} de ${formatValue(total)} jogos` }),
      ]),
      node("div", { class: "home-progress-track" }, [node("i", { style: `width:${percent.toFixed(1)}%`, "aria-hidden": "true" })]),
    ]);
  }

  function homeSummaryStrip(summary) {
    const metrics = [
      ["Gols", summary.goals],
      ["Gols por jogo", summary.goals_per_match],
      ["xG total", summary.xg],
      ["xG por jogo", summary.xg_per_match],
      ["Finalizações", summary.shots],
      ["Conversão média", summary.shot_conversion, metricAvailable(summary.shot_conversion) ? `${formatValue(summary.shot_conversion)}%` : null],
      ["Clean sheets", summary.clean_sheets],
      ["Jogadores utilizados", summary.players],
    ].filter(([, value]) => value !== null && value !== undefined);
    if (!metrics.length) return null;
    return section("Resumo da edição", null, node("div", { class: "home-summary-block" }, [
      node("div", { class: "home-summary-strip" }, metrics.map(([metric, value, display]) =>
        node("div", { class: "home-summary-metric" }, [
          node("strong", { text: display || formatValue(value) }),
          node("span", { text: metric }),
        ])
      )),
      homeCompetitionProgress(summary),
    ].filter(Boolean)), "home-summary-section");
  }

  function knockoutSideNode(side, className = "") {
    if (side?.defined && side?.team_name) return teamLabel(side.team_name, `home-bracket-team ${className}`.trim());
    const placeholderText = translateTeamsInText(side?.placeholder || "A definir");
    return node("span", { class: `home-bracket-team is-placeholder ${className}`.trim(), title: placeholderText }, [
      node("span", { text: placeholderText }),
    ]);
  }

  function homeFriendlyKickoff(value) {
    const date = new Date(value || "");
    if (Number.isNaN(date.getTime())) return "Horário a definir";
    const timezone = "America/Sao_Paulo";
    const dateKey = input => new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
    }).format(input);
    const now = new Date();
    const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
    const time = new Intl.DateTimeFormat("pt-BR", { timeZone: timezone, hour: "2-digit", minute: "2-digit" }).format(date);
    if (dateKey(date) === dateKey(now)) return `Hoje, ${time}`;
    if (dateKey(date) === dateKey(tomorrow)) return `Amanhã, ${time}`;
    const shortDate = new Intl.DateTimeFormat("pt-BR", { timeZone: timezone, day: "2-digit", month: "2-digit" }).format(date);
    return `${shortDate}, ${time}`;
  }

  function teamNameWithArticle(team) {
    const feminine = new Set([
      "Argentina", "Australia", "Austria", "Belgium", "Bosnia & Herzegovina",
      "Colombia", "Côte d'Ivoire", "Croatia", "Denmark", "France", "Germany", "Ghana",
      "Netherlands", "Norway", "Poland", "Saudi Arabia", "Scotland", "South Africa",
      "South Korea", "Spain", "Sweden", "Switzerland", "Tunisia", "Türkiye", "Turkey",
      "Ukraine",
    ]);
    if (team === "USA" || team === "United States") return `os ${displayTeamName(team)}`;
    return `${feminine.has(team) ? "a" : "o"} ${displayTeamName(team)}`;
  }

  function homeQualifiedStory(item) {
    const winner = displayTeamName(item.winner_name);
    const eliminated = teamNameWithArticle(item.eliminated_name);
    const score = item.score_label || "placar não informado";
    if (item.decided_by === "penalties") {
      const regulation = score.split(" (")[0];
      return `${winner} avançou nos pênaltis após empate por ${regulation} contra ${eliminated}.`;
    }
    if (item.decided_by === "extra_time") return `${winner} avançou na prorrogação após vencer ${eliminated} por ${score.replace(" (prorrogação)", "")}.`;
    return `${winner} avançou após vencer ${eliminated} por ${score}.`;
  }

  function homeBracketMatch(match, phase = null) {
    const canOpen = Boolean(match?.match_id);
    const hasPlaceholder = !match?.home?.defined || !match?.away?.defined;
    const date = match?.kickoff_at || match?.match_date;
    const status = competitionMatchStatus(match);
    const centerText = status === "Encerrado" || homeMatchIsLive(match)
      ? status
      : (date ? homeFriendlyKickoff(date) : "A definir");
    const outcome = match?.decided_by === "penalties" && match?.winner_name
      ? `${displayTeamName(match.winner_name)} nos pênaltis`
      : null;
    return node("button", {
      type: "button",
      class: `home-bracket-match${hasPlaceholder ? " has-placeholder" : ""}`,
      disabled: !canOpen,
      onclick: canOpen ? () => openMatchQuickView({ ...match, stage: phase || match.stage }) : null,
    }, [
      knockoutSideNode(match?.home, "home"),
      node("strong", { class: "home-bracket-center", text: centerText }),
      knockoutSideNode(match?.away, "away"),
      outcome ? node("small", { class: "home-bracket-outcome", text: outcome }) : null,
    ]);
  }

  function homePulse(pulse) {
    const today = pulse?.today_matches || [];
    const classified = pulse?.classified_recent || [];
    const next = pulse?.next_matchups || [];
    if (!pulse?.current_phase && !today.length && !classified.length && !next.length) return null;
    const columns = [
      node("article", { class: "home-pulse-column" }, [
        node("header", {}, [node("small", { text: "Horários em Brasília" }), node("h3", { text: "Agenda de hoje" })]),
        today.length
          ? node("div", { class: "home-pulse-list" }, today.slice(0, 3).map((match, index) => compactMatchRow(match, { featured: index === 0 })))
          : node("p", { class: "home-empty-line", text: "Não há jogos programados para hoje." }),
      ]),
      node("article", { class: "home-pulse-column" }, [
        node("header", {}, [node("small", { text: "Consequências" }), node("h3", { text: "Quem avançou" })]),
        classified.length
          ? node("div", { class: "home-pulse-list" }, classified.slice(0, 4).map(item => {
            const home = item.match?.home, away = item.match?.away;
            const hasScore = metricAvailable(item.match?.home_score) && metricAvailable(item.match?.away_score);
            return node("button", {
              type: "button", class: "home-pulse-story", onclick: () => openMatchQuickView(item.match),
            }, [
              node("div", { class: "home-pulse-story-score" }, [
                knockoutSideNode(home, "home"),
                hasScore
                  ? scoreText(item.match.home_score, item.match.away_score, { homeName: home?.team_name, awayName: away?.team_name })
                  : null,
                knockoutSideNode(away, "away"),
              ]),
              node("span", {}, [
                node("strong", { text: displayTeamName(item.winner_name) }),
                node("small", { text: homeQualifiedStory(item) }),
                node("em", { text: [item.phase, item.score_label].filter(Boolean).join(" · ") }),
              ]),
            ]);
          }))
          : node("p", { class: "home-empty-line", text: "As próximas classificações aparecerão aqui." }),
      ]),
      node("article", { class: "home-pulse-column" }, [
        node("header", {}, [node("small", { text: pulse?.next_phase || "Próxima fase" }), node("h3", { text: "Próximos confrontos" })]),
        next.length
          ? node("div", { class: "home-pulse-list" }, next.map(match => homeBracketMatch(match)))
          : node("p", { class: "home-empty-line", text: "Os próximos confrontos ainda estão sendo definidos." }),
      ]),
    ];
    return node("div", { class: "home-pulse" }, [
      node("div", { class: "home-pulse-phase" }, [
        node("span", {}, [node("small", { text: "Fase atual" }), node("strong", { class: "home-phase-now", text: pulse.current_phase || "Em andamento" })]),
        pulse.next_phase ? node("span", { class: "home-phase-next" }, [node("small", { text: "Na sequência" }), node("strong", { text: pulse.next_phase })]) : null,
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
      group_stage: "Fase de grupos", round_of_32: "Fase de 32",
      round_of_16: "Oitavas de final", quarter_final: "Quartas de final",
      semi_final: "Semifinal", semifinal: "Semifinal",
      third_place: "Disputa de 3º lugar", final: "Final",
    };
    return labels[stage] || "Copa do Mundo 2026";
  }

  function compactMatchSide(side, rawName, className) {
    if (side) {
      if (side.defined && side.team_name) return teamLabel(side.team_name, className);
      const placeholderText = translateTeamsInText(side.placeholder || "A definir");
      return node("span", { class: `${className} is-placeholder`, title: placeholderText }, [
        node("span", { text: placeholderText }),
      ]);
    }
    if (rawName && !countryMeta[rawName]) {
      // Placeholder de confronto futuro ("Winner of X x Y") — traduz os nomes
      // embutidos e não tenta desenhar bandeira.
      const translated = translateTeamsInText(rawName).replace("Winner of", "Vencedor de");
      return node("span", { class: `${className} is-placeholder`, title: translated }, [node("span", { text: translated })]);
    }
    return teamLabel(rawName, className);
  }

  function compactMatchSideLabel(side, rawName) {
    if (side) return side.defined && side.team_name ? displayTeamName(side.team_name) : translateTeamsInText(side.placeholder || "A definir");
    return displayTeamName(rawName);
  }

  function compactMatchRow(match, { featured = false } = {}) {
    const homeName = match?.home?.team_name || match?.home_team;
    const awayName = match?.away?.team_name || match?.away_team;
    const context = homeStageLabel(match);
    return node("button", {
      type: "button",
      class: `home-match-row${featured ? " is-featured" : ""}`,
      style: matchPalette(homeName, awayName),
      onclick: () => openMatchQuickView(match),
      "aria-label": `${compactMatchSideLabel(match?.home, match?.home_team)} contra ${compactMatchSideLabel(match?.away, match?.away_team)}. ${competitionMatchStatus(match)}.`,
    }, [
      node("span", { class: "home-match-meta" }, [
        node("b", { text: competitionMatchStatus(match) }),
        node("time", { dateTime: match?.match_date || "", title: "Horários em Brasília", text: homeFriendlyKickoff(match?.match_date) }),
      ]),
      node("span", { class: "home-match-scoreline" }, [
        compactMatchSide(match?.home, match?.home_team, "home-match-team home"),
        node("strong", { class: "home-match-score", text: homeMatchCenter(match) }),
        compactMatchSide(match?.away, match?.away_team, "home-match-team away"),
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
    if (metric === "goals") return `${value} ${singularizeUnit(parsed, "gols")}`;
    if (metric === "assists") return `${value} assist.`;
    if (metric === "shots") return `${value} ${singularizeUnit(parsed, "chutes")}`;
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
    const open = entity === "player" && item.player_id
      ? () => goToProfile("player", item.player_id)
      : entity === "team" && item.team_id
        ? () => goToProfile("team", item.team_id)
        : () => openHomeEntityQuickView(item, entity);
    return node("button", { type: "button", class: "home-ranking-row", onclick: open }, [
      node("span", { class: "home-rank", text: String(index + 1) }),
      homeRankingEntity(item, entity),
      node("strong", { class: `home-ranking-value ${homeRankingValueClass(item, metric)}`.trim(), text: homeRankingValue(item, metric) }),
    ]);
  }

  function homeRankingPanel({ kicker, title, rows, metric, entity }) {
    return node("article", { class: "home-ranking-panel" }, [
      node("button", { type: "button", class: "home-ranking-open", onclick: () => openRankingQuickView({ kicker, title, rows, metric, entity }) }, [
        node("span", {}, [node("small", { text: kicker }), node("strong", { text: title })]),
        node("span", { class: "home-ranking-expand", text: "Ver ranking completo" }),
      ]),
      node("div", { class: "home-ranking-list" }, rows.slice(0, 5).map((item, index) => homeRankingRow(item, index, metric, entity))),
    ]);
  }

  function openPlayerQuickView(player) {
    if (player?.player_id) {
      goToProfile("player", player.player_id);
      return;
    }
    openQuickView({
      kicker: "Resumo do jogador",
      titleContent: node("span", { class: "quick-entity-title" }, [flagNode(player, "flag-medium"), node("span", { text: personName(player) })]),
      rows: [
        ["Seleção", teamName(player)], ["Posição", resolvedPlayerPosition(player)],
        ["Jogos", player.games], ["Minutos", player.minutes_played],
        ["Gols", player.goals], ["Assistências", player.assists],
        ["xG", player.xg], ["Rating", player.rating],
      ],
      actionLabel: player.player_id ? "Abrir jogador" : null,
      onAction: player.player_id ? () => goToProfile("player", player.player_id) : null,
    });
  }

  function openHomeTeamQuickView(team) {
    if (team?.team_id) {
      goToProfile("team", team.team_id);
      return;
    }
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
      onAction: team.team_id ? () => goToProfile("team", team.team_id) : null,
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
    if (metric.id === "goals_per_90") return `${formatValue(value)} gols/90`;
    if (metric.id === "most_on_target") return `${formatValue(value)} no alvo`;
    if (metric.id === "most_balanced_xg") return `Diferença de xG: ${value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (metric.id === "goals_minus_xg") return `${value > 0 ? "+" : ""}${formatValue(value)} gols - xG`;
    if (metric.unit === "xG") return `${formatValue(value)} xG`;
    return `${formatValue(value)} ${singularizeUnit(value, metric.unit) || ""}`.trim();
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
      ["players", "Jogadores", "Eficiência e influência individual", "Eficiência por 90, qualidade das chances e conversão."],
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
      onclick: () => {
        const pages = { players: "players", teams: "teams", matches: "matches" };
        if (pages[category.key]) goTo(state.year, pages[category.key]);
        else openDiscoveryCategoryView(category);
      },
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
      team ? { kicker: "Seleção em destaque", entity: "team", item: team, reason: `${formatValue(team.xg)} xG e saldo de ${signedStandingValue(team.goal_difference)} gols na Copa.`, stats: [["Jogos", team.played], ["GP", team.goals_for], ["GC", team.goals_against]] } : null,
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
    const fragment = dashboardShell("Seleções", "Compare produção, controle, eficiência e solidez defensiva das seleções na Copa 2026.", data);
    const experience = teamAnalysisExperience(data);
    if (experience) fragment.append(experience);
    else fragment.append(emptyState("Seleções indisponíveis", "As métricas coletivas ainda não estão disponíveis."));
    els.view.replaceChildren(fragment);
  }

  function renderPlayers(data) {
    const fragment = dashboardShell("Jogadores", "Compare produção, eficiência e perfil de atuação na Copa 2026.", data);
    const experience = playerOverviewExperience(data);
    if (experience) fragment.append(experience);
    else fragment.append(emptyState("Jogadores indisponíveis", "As estatísticas individuais ainda não estão disponíveis."));
    els.view.replaceChildren(fragment);
  }

  function compactAnalysisSummary(metrics) {
    const rows = metrics.filter(([, value]) => value !== null && value !== undefined);
    return node("dl", { class: "analysis-summary-strip" }, rows.map(([labelText, value]) => node("div", {}, [
      node("dt", { text: labelText }), node("dd", { text: formatValue(value) }),
    ])));
  }

  function playerMetricDefinitions() {
    return [
      { category: "Ataque", id: "goals", title: "Gols", description: "Total de gols marcados.", value: row => number(row.goals), unit: "gols" },
      { category: "Ataque", id: "assists", title: "Assistências", description: "Passes que terminaram em gol.", value: row => number(row.assists), unit: "assist." },
      { category: "Ataque", id: "xg", title: "xG", description: "Qualidade acumulada das finalizações.", value: row => number(row.xg), unit: "xG" },
      { category: "Ataque", id: "xa", title: "xA", description: "Qualidade acumulada dos passes que geraram finalizações.", value: row => number(row.xa), unit: "xA" },
      { category: "Ataque", id: "shots", title: "Finalizações", description: "Volume total de chutes.", value: row => number(row.shots), unit: "chutes" },
      { category: "Ataque", id: "shots_on_target", title: "Finalizações no alvo", description: "Chutes que exigiram defesa ou terminaram em gol.", value: row => number(row.shots_on_target), unit: "no alvo" },
      { category: "Ataque", id: "goals_minus_xg", title: "Gols - xG", description: "Diferença entre gols marcados e gols esperados.", value: row => number(row.goals_minus_xg), unit: "", signed: true },
      { category: "Ataque", id: "xg_per_shot", title: "xG por finalização", description: "Qualidade média das chances.", eligibility: "Mínimo de 5 finalizações", eligible: row => number(row.shots) >= 5, value: row => number(row.xg_per_shot), unit: "xG" },
      { category: "Ataque", id: "conversion", title: "Conversão", description: "Percentual de chutes transformados em gol.", eligibility: "Mínimo de 5 finalizações", eligible: row => number(row.shots) >= 5, value: row => number(row.shot_conversion), unit: "%" },
      { category: "Por 90", id: "goal_involvements_per_90", title: "Participações em gols por 90", description: "Gols e assistências normalizados para 90 minutos.", eligibility: "Mínimo de 90 minutos", eligible: row => number(row.minutes_played) >= 90, value: row => number(row.goal_involvements_per_90), unit: "por 90" },
      { category: "Por 90", id: "goals_per_90", title: "Gols por 90", description: "Gols normalizados para uma partida completa de 90 minutos.", eligibility: "Mínimo de 90 minutos e 2 gols", eligible: row => number(row.minutes_played) >= 90 && number(row.goals) >= 2, value: row => number(row.goals_per_90), unit: "por 90" },
      { category: "Por 90", id: "assists_per_90", title: "Assistências por 90", description: "Assistências normalizadas para 90 minutos.", eligibility: "Mínimo de 90 minutos", eligible: row => number(row.minutes_played) >= 90, value: row => number(row.assists_per_90), unit: "por 90" },
      { category: "Por 90", id: "xg_per_90", title: "xG por 90", description: "Produção de xG normalizada para 90 minutos.", eligibility: "Mínimo de 90 minutos e 3 finalizações", eligible: row => number(row.minutes_played) >= 90 && number(row.shots) >= 3, value: row => number(row.xg_per_90), unit: "por 90" },
      { category: "Por 90", id: "xa_per_90", title: "xA por 90", description: "Produção de xA normalizada para 90 minutos.", eligibility: "Mínimo de 90 minutos", eligible: row => number(row.minutes_played) >= 90, value: row => number(row.xa_per_90), unit: "por 90" },
      { category: "Por 90", id: "shots_per_90", title: "Finalizações por 90", description: "Finalizações normalizadas para 90 minutos.", eligibility: "Mínimo de 90 minutos", eligible: row => number(row.minutes_played) >= 90, value: row => number(row.shots_per_90), unit: "por 90" },
      { category: "Criação e passe", id: "key_passes", title: "Passes para finalização", description: "Passes que terminaram em chute.", value: row => number(row.key_passes), unit: "passes" },
      { category: "Criação e passe", id: "key_passes_per_90", title: "Passes para finalização por 90", description: "Passes para finalização normalizados para 90 minutos.", eligibility: "Mínimo de 90 minutos", eligible: row => number(row.minutes_played) >= 90, value: row => number(row.key_passes_per_90), unit: "por 90" },
      { category: "Criação e passe", id: "accurate_passes", title: "Passes certos", description: "Total de passes completos.", value: row => number(row.accurate_passes), unit: "passes" },
      { category: "Criação e passe", id: "pass_accuracy", title: "Precisão de passe", description: "Percentual de passes completos.", eligibility: "Mínimo de 30 passes tentados", eligible: row => number(row.passes) >= 30, value: row => number(row.pass_accuracy), unit: "%" },
      { category: "Criação e passe", id: "long_pass_accuracy", title: "Precisão em passes longos", description: "Percentual de bolas longas completas.", eligibility: "Mínimo de 5 passes longos tentados", eligible: row => number(row.total_long_balls) >= 5, value: row => number(row.long_pass_accuracy), unit: "%" },
      { category: "Criação e passe", id: "cross_accuracy", title: "Precisão em cruzamentos", description: "Percentual de cruzamentos certos.", eligibility: "Mínimo de 5 cruzamentos tentados", eligible: row => number(row.total_crosses) >= 5, value: row => number(row.cross_accuracy), unit: "%" },
      { category: "Defesa", id: "defensive_actions", title: "Ações defensivas", description: "Soma de desarmes, interceptações e cortes.", value: row => number(row.defensive_actions), unit: "ações" },
      { category: "Defesa", id: "tackles", title: "Desarmes", description: "Total de desarmes realizados.", value: row => number(row.tackles), unit: "desarmes" },
      { category: "Defesa", id: "interceptions", title: "Interceptações", description: "Total de interceptações.", value: row => number(row.interceptions), unit: "interc." },
      { category: "Defesa", id: "clearances", title: "Cortes", description: "Total de cortes defensivos.", value: row => number(row.clearances), unit: "cortes" },
      { category: "Defesa", id: "duels_won", title: "Duelos vencidos", description: "Total de duelos ganhos.", value: row => number(row.duels_won), unit: "duelos" },
      { category: "Defesa", id: "defensive_actions_per_90", title: "Ações defensivas por 90", description: "Ações defensivas normalizadas para 90 minutos.", eligibility: "Mínimo de 90 minutos", eligible: row => number(row.minutes_played) >= 90, value: row => number(row.defensive_actions_per_90), unit: "por 90" },
      { category: "Goleiros", id: "saves", title: "Defesas", description: "Finalizações defendidas pelo goleiro.", eligibility: "Somente goleiros com pelo menos 90 minutos", eligible: row => positionLabel(row.position) === "GOL" && number(row.minutes_played) >= 90, value: row => number(row.saves), unit: "defesas" },
      { category: "Goleiros", id: "saves_per_90", title: "Defesas por 90", description: "Defesas normalizadas para 90 minutos.", eligibility: "Somente goleiros com pelo menos 90 minutos", eligible: row => positionLabel(row.position) === "GOL" && number(row.minutes_played) >= 90, value: row => number(row.saves_per_90), unit: "por 90" },
      { category: "Goleiros", id: "rating", title: "Rating médio", description: "Nota média nas partidas do recorte.", eligibility: "Somente goleiros com pelo menos 90 minutos", eligible: row => positionLabel(row.position) === "GOL" && number(row.minutes_played) >= 90, value: row => number(row.rating), unit: "" },
    ];
  }

  function teamMetricDefinitions() {
    return [
      { category: "Ataque", id: "goals_for", title: "Gols marcados", description: "Produção ofensiva no placar.", value: row => number(row.goals_for), unit: "gols" },
      { category: "Ataque", id: "goals_per_game", title: "Gols por jogo", description: "Média de gols marcados por partida.", eligibility: "Mínimo de 2 jogos", eligible: row => number(row.played) >= 2, value: row => number(row.goals_per_game), unit: "por jogo" },
      { category: "Ataque", id: "xg", title: "xG criado", description: "Qualidade total das chances produzidas.", value: row => number(row.xg), unit: "xG" },
      { category: "Ataque", id: "xg_per_game", title: "xG criado por jogo", description: "xG total dividido pelos jogos disputados.", eligibility: "Mínimo de 2 jogos", eligible: row => number(row.played) >= 2, value: row => number(row.xg_per_game), unit: "por jogo" },
      { category: "Ataque", id: "shots", title: "Finalizações", description: "Volume total de finalizações.", value: row => number(row.shots), unit: "chutes" },
      { category: "Ataque", id: "shots_per_game", title: "Finalizações por jogo", description: "Volume ofensivo médio.", eligibility: "Mínimo de 2 jogos", eligible: row => number(row.played) >= 2, value: row => number(row.shots_per_game), unit: "por jogo" },
      { category: "Ataque", id: "shots_on_target", title: "Finalizações no alvo", description: "Chutes que exigiram defesa ou terminaram em gol.", value: row => number(row.shots_on_target), unit: "no alvo" },
      { category: "Ataque", id: "conversion", title: "Conversão", description: "Percentual de finalizações transformadas em gol.", eligibility: "Mínimo de 10 finalizações", eligible: row => number(row.shots) >= 10, value: row => number(row.conversion), unit: "%" },
      { category: "Defesa", id: "goals_against", title: "Menos gols sofridos", description: "Solidez defensiva no placar.", value: row => number(row.goals_against), unit: "gols", ascending: true },
      { category: "Defesa", id: "goals_against_per_game", title: "Gols sofridos por jogo", description: "Média de gols sofridos por partida.", eligibility: "Mínimo de 2 jogos", eligible: row => number(row.played) >= 2, value: row => number(row.goals_against_per_game), unit: "por jogo", ascending: true },
      { category: "Defesa", id: "xga", title: "Menor xG cedido", description: "Qualidade das chances concedidas.", value: row => number(row.xga), unit: "xG", ascending: true },
      { category: "Defesa", id: "xga_per_game", title: "xG cedido por jogo", description: "xG adversário dividido pelos jogos disputados.", eligibility: "Mínimo de 2 jogos", eligible: row => number(row.played) >= 2, value: row => number(row.xga_per_game), unit: "por jogo", ascending: true },
      { category: "Defesa", id: "shots_against", title: "Finalizações sofridas", description: "Total de chutes concedidos aos adversários.", value: row => number(row.shots_against), unit: "chutes", ascending: true },
      { category: "Defesa", id: "shots_against_per_game", title: "Finalizações sofridas por jogo", description: "Chutes concedidos em média por partida.", eligibility: "Mínimo de 2 jogos", eligible: row => number(row.played) >= 2, value: row => number(row.shots_against_per_game), unit: "por jogo", ascending: true },
      { category: "Domínio", id: "goal_difference", title: "Saldo de gols", description: "Gols marcados menos gols sofridos.", value: row => number(row.goal_difference), unit: "gols", signed: true },
      { category: "Domínio", id: "xg_difference", title: "Saldo de xG", description: "xG criado menos xG cedido.", value: row => number(row.xg_difference), unit: "xG", signed: true },
      { category: "Domínio", id: "shot_difference", title: "Saldo de finalizações", description: "Finalizações feitas menos finalizações sofridas.", value: row => number(row.shot_difference), unit: "chutes", signed: true },
      { category: "Domínio", id: "goals_minus_xg", title: "Gols - xG", description: "Diferença entre gols marcados e gols esperados.", value: row => number(row.goals_minus_xg), unit: "", signed: true },
      { category: "Posse e passe", id: "average_possession", title: "Posse média", description: "Média de posse de bola nas partidas com dados disponíveis.", value: row => number(row.average_possession), unit: "%" },
      { category: "Posse e passe", id: "accurate_passes", title: "Passes certos", description: "Total de passes completos.", value: row => number(row.accurate_passes), unit: "passes" },
      { category: "Posse e passe", id: "pass_accuracy", title: "Precisão de passe", description: "Percentual de passes completos.", eligibility: "Mínimo de 100 passes tentados", eligible: row => number(row.passes) >= 100, value: row => number(row.pass_accuracy), unit: "%" },
      { category: "Sem bola", id: "recoveries", title: "Recuperações", description: "Bolas recuperadas pela seleção.", value: row => number(row.recoveries), unit: "recup." },
      { category: "Sem bola", id: "recoveries_per_game", title: "Recuperações por jogo", description: "Recuperações médias por partida.", eligibility: "Mínimo de 2 jogos", eligible: row => number(row.played) >= 2, value: row => number(row.recoveries_per_game), unit: "por jogo" },
      { category: "Sem bola", id: "tackles", title: "Desarmes", description: "Total de desarmes realizados.", value: row => number(row.tackles), unit: "desarmes" },
      { category: "Sem bola", id: "interceptions", title: "Interceptações", description: "Total de interceptações.", value: row => number(row.interceptions), unit: "interc." },
      { category: "Sem bola", id: "clearances", title: "Cortes", description: "Total de cortes defensivos.", value: row => number(row.clearances), unit: "cortes" },
      { category: "Disciplina", id: "fouls_per_game", title: "Menos faltas por jogo", description: "Faltas médias cometidas por partida.", eligibility: "Mínimo de 2 jogos", eligible: row => number(row.played) >= 2, value: row => number(row.fouls_per_game), unit: "por jogo", ascending: true },
      { category: "Disciplina", id: "yellow_cards_per_game", title: "Menos cartões amarelos por jogo", description: "Cartões amarelos médios recebidos por partida.", eligibility: "Mínimo de 2 jogos", eligible: row => number(row.played) >= 2, value: row => number(row.yellow_cards_per_game), unit: "por jogo", ascending: true },
      { category: "Disciplina", id: "red_cards", title: "Menos cartões vermelhos", description: "Total de cartões vermelhos recebidos na competição.", value: row => number(row.red_cards), unit: "vermelhos", ascending: true },
    ];
  }

  // Documented tie-break for every ranking in the product: when the primary metric ties, order
  // alphabetically (pt-BR) by player/team name. Alphabetical is the only criterion that applies
  // uniformly to any metric (attack, defense, discipline...) without special-casing — a metric
  // specific tie-break (e.g. "lowest xG conceded" for goals-against) wouldn't generalize to a
  // metric like duels won, so ties would still look arbitrary somewhere else.
  function rankingTieBreakName(row) {
    return row?.player_name || row?.team_name || "";
  }

  function analysisMetricRows(items, definition) {
    return items
      .filter(row => !definition.eligible || definition.eligible(row))
      .map(row => ({ ...row, analysis_value: definition.value(row) }))
      .filter(row => {
        const value = number(row.analysis_value);
        // For "lower is better" metrics (fewest fouls, fewest cards conceded, etc.) zero is
        // usually the headline-worthy value, not a sign of "no data" — only exclude zero for
        // regular (higher-is-better) metrics, where it typically means no contribution at all.
        if (value === null) return false;
        return definition.ascending || value !== 0;
      })
      .sort((left, right) => {
        const diff = definition.ascending ? left.analysis_value - right.analysis_value : right.analysis_value - left.analysis_value;
        return diff !== 0 ? diff : rankingTieBreakName(left).localeCompare(rankingTieBreakName(right), "pt-BR");
      });
  }

  function analysisMetricValue(row, definition) {
    const value = number(row.analysis_value);
    if (value === null) return "—";
    const formatted = definition.signed && value > 0 ? `+${formatValue(value)}` : formatValue(value);
    const unit = singularizeUnit(value, definition.unit);
    return unit === "%" ? `${formatted}%` : `${formatted}${unit ? ` ${unit}` : ""}`;
  }

  function analysisRankingRow(row, index, definition, entity) {
    return node("button", { type: "button", class: "analysis-ranking-row", onclick: () => goToProfile(entity, entity === "player" ? row.player_id : row.team_id) }, [
      node("span", { class: "home-rank", text: index + 1 }),
      homeRankingEntity(row, entity),
      node("strong", { class: definition.signed ? homeRankingValueClass({ xg_difference: row.analysis_value }, "xg_difference") : "", text: analysisMetricValue(row, definition) }),
    ]);
  }

  function openAnalysisRanking(definition, rows, entity) {
    const list = node("div", { class: "analysis-ranking-full-list" });
    const search = node("input", { type: "search", placeholder: entity === "player" ? "Buscar jogador" : "Buscar seleção", class: "analysis-ranking-search" });
    const draw = () => {
      const query = search.value.trim().toLocaleLowerCase("pt-BR");
      const filtered = rows.filter(row => !query || `${entity === "player" ? personName(row) : teamName(row)} ${displayTeamName(row.team_name)}`.toLocaleLowerCase("pt-BR").includes(query));
      list.replaceChildren(...filtered.map((row, index) => analysisRankingRow(row, index, definition, entity)));
    };
    search.oninput = draw;
    draw();
    openQuickView({
      kicker: entity === "player" ? "Ranking de jogadores" : "Ranking de seleções",
      titleContent: definition.title,
      rows: [], layout: "modal", actionLabel: null, onAction: null,
      extra: node("section", { class: "analysis-ranking-detail" }, [
        node("p", { text: definition.description }),
        definition.eligibility ? node("small", { text: definition.eligibility }) : null,
        search, list,
      ]),
    });
  }

  function analysisRankingPanels(items, definitions, entity) {
    return node("div", { class: "analysis-ranking-grid" }, definitions.map(definition => {
      const rows = analysisMetricRows(items, definition);
      if (!rows.length) return null;
      return node("article", { class: "analysis-ranking-panel" }, [
        node("header", {}, [node("span", {}, [node("small", { text: entity === "player" ? "Jogadores" : "Seleções" }), node("h3", { text: definition.title })]), node("button", { type: "button", text: "Ver todos", onclick: () => openAnalysisRanking(definition, rows, entity) })]),
        node("div", {}, rows.slice(0, 5).map((row, index) => analysisRankingRow(row, index, definition, entity))),
      ]);
    }).filter(Boolean));
  }

  function playerRankingPanels(players) {
    return playerRankingExplorer(players);
  }

  function playerRankingExplorer(players) {
    const definitions = playerMetricDefinitions();
    const categories = [...new Set(definitions.map(definition => definition.category || "Geral"))]
      .filter(category => definitions.some(definition => (definition.category || "Geral") === category && analysisMetricRows(players, definition).length));
    if (!categories.length) return null;
    let activeCategory = categories[0];
    let activeMetric = null;
    const tabs = attachTabListKeyNav(node("div", { class: "segmented-control analysis-ranking-tabs", role: "tablist", "aria-label": "Categorias de ranking" }));
    const metricSelect = node("select", { "aria-label": "Métrica do ranking" });
    const host = node("div", { class: "player-ranking-single" });
    const availableDefinitions = () => definitions.filter(definition => (definition.category || "Geral") === activeCategory && analysisMetricRows(players, definition).length);
    const drawMetric = () => {
      const available = availableDefinitions();
      const definition = available.find(item => item.id === activeMetric) || available[0];
      if (!definition) return;
      activeMetric = definition.id;
      metricSelect.replaceChildren(...available.map(item => node("option", { value: item.id, text: item.title })));
      metricSelect.value = activeMetric;
      host.replaceChildren(analysisRankingPanels(players, [definition], "player"));
    };
    const drawCategory = () => {
      tabs.querySelectorAll("button").forEach(button => {
        const selected = button.dataset.category === activeCategory;
        button.classList.toggle("is-active", selected);
        button.setAttribute("aria-selected", String(selected));
      });
      activeMetric = null;
      drawMetric();
    };
    tabs.replaceChildren(...categories.map(category => node("button", {
      type: "button", text: category, role: "tab", "data-category": category,
      onclick: () => { activeCategory = category; drawCategory(); },
    })));
    metricSelect.onchange = event => { activeMetric = event.target.value; drawMetric(); };
    drawCategory();
    return node("div", { class: "analysis-ranking-explorer player-ranking-explorer" }, [
      node("div", { class: "player-ranking-controls" }, [tabs, node("label", {}, [node("span", { text: "Métrica" }), metricSelect])]),
      host,
    ]);
  }

  function analysisChartPanel(title, description, content, meta = null) {
    return node("article", { class: "analysis-chart-panel", "data-design-component": "chart-panel" }, [
      node("header", {}, [node("span", {}, [node("h3", { text: title }), node("p", { text: description })]), meta]),
      content,
    ]);
  }

  function playerEditionHighlights(players) {
    // Seis categorias com dedupe: o mesmo jogador não repete entre cards —
    // se lidera duas listas, a segunda vai para o próximo nome distinto.
    const used = new Set();
    const pick = (metric, eligible = () => true) => {
      const row = [...players]
        .filter(player => eligible(player) && number(player[metric]) !== null && !used.has(player.player_id))
        .sort((left, right) => number(right[metric]) - number(left[metric]))[0];
      if (row) used.add(row.player_id);
      return row;
    };
    const scorer = pick("goals");
    const topXg = pick("xg");
    const creator = pick("xa");
    const efficient = pick("goals_minus_xg", player => number(player.shots) >= 5);
    const volume = pick("shots");
    const keeper = pick("saves", player => (player.macroposition === "Goleiro" || positionLabel(player.position) === "GOL") && number(player.saves) > 0);
    const highlights = [
      scorer ? { kicker: "Artilheiro", player: scorer, value: `${formatValue(scorer.goals)} gols`, detail: `${formatValue(scorer.xg)} xG · ${formatValue(scorer.minutes_played)} min` } : null,
      topXg ? { kicker: "Maior xG", player: topXg, value: `${formatValue(topXg.xg)} xG`, detail: `${formatValue(topXg.goals)} gols · ${formatValue(topXg.shots)} finalizações` } : null,
      creator ? { kicker: "Melhor criador", player: creator, value: `${formatValue(creator.xa)} xA`, detail: `${formatValue(creator.assists)} assistências · ${formatValue(creator.key_passes)} passes para finalização` } : null,
      efficient ? { kicker: "Acima do esperado", player: efficient, value: `${number(efficient.goals_minus_xg) > 0 ? "+" : ""}${formatValue(efficient.goals_minus_xg)} gols - xG`, detail: `${formatValue(efficient.goals)} gols em ${formatValue(efficient.shots)} finalizações` } : null,
      volume ? { kicker: "Maior volume", player: volume, value: `${formatValue(volume.shots)} finalizações`, detail: `${formatValue(volume.shots_on_target)} no alvo · ${formatValue(volume.xg)} xG` } : null,
      keeper ? { kicker: "Goleiro em destaque", player: keeper, value: `${formatValue(keeper.saves)} defesas`, detail: `${formatValue(keeper.minutes_played)} min · rating ${formatValue(keeper.rating)}` } : null,
    ].filter(Boolean);
    if (!highlights.length) return null;
    return node("div", { class: "player-editorial-highlights" }, highlights.map(({ kicker, player, value, detail }) => node("button", {
      type: "button", onclick: () => goToProfile("player", player.player_id),
    }, [
      node("small", { text: kicker }),
      node("strong", {}, [flagNode(player), node("span", { text: personName(player) })]),
      node("b", { text: value }),
      node("span", { text: detail }),
    ])));
  }

  function playerComparisonMap(rows, onSelect) {
    const modes = [
      { id: "goals", label: "Gols × xG", description: "Quem converteu acima ou abaixo da produção esperada.", render: () => playerScatterPlot(rows, { onSelect }) },
      { id: "creation", label: "xG × xA", description: "Quem combinou presença para finalizar e capacidade de criação.", render: () => playerSecondaryScatterPlot(rows, "creation", onSelect) },
      { id: "volume", label: "Finalizações × xG", description: "Como volume e qualidade das chances se relacionam.", render: () => playerSecondaryScatterPlot(rows, "volume", onSelect) },
      { id: "shot_efficiency", label: "Finalizações × Conversão", description: "Identifica quem tem poucas chances e alto aproveitamento — leitura diferente de Gols x xG.", render: () => playerSecondaryScatterPlot(rows, "shot_efficiency", onSelect) },
      { id: "duels", label: "Duelos disputados × % ganhos", description: "Eficiência em disputas físicas na competição.", render: () => playerSecondaryScatterPlot(rows, "duels", onSelect) },
      { id: "per90", label: "Gols por 90 × xG por 90", description: "Produção normalizada por minutos jogados, sem o viés de titulares com mais tempo em campo.", render: () => playerSecondaryScatterPlot(rows, "per90", onSelect) },
    ];
    let active = modes[0];
    const host = node("div", { class: "player-comparison-chart" });
    const description = node("p");
    const tabs = attachTabListKeyNav(node("div", { class: "segmented-control player-comparison-switch", role: "tablist", "aria-label": "Métrica do mapa de comparação" }));
    const draw = () => {
      tabs.querySelectorAll("button").forEach(button => {
        const selected = button.dataset.mode === active.id;
        button.classList.toggle("is-active", selected);
        button.setAttribute("aria-selected", String(selected));
      });
      description.textContent = active.description;
      host.replaceChildren(active.render());
    };
    tabs.replaceChildren(...modes.map(mode => node("button", {
      type: "button", text: mode.label, role: "tab", "data-mode": mode.id,
      onclick: () => { active = mode; draw(); },
    })));
    draw();
    return node("div", { class: "player-comparison-map" }, [node("div", { class: "player-comparison-toolbar" }, [tabs, description]), host]);
  }

  function playerOverviewExperience(data) {
    const players = (data.items || []).filter(player => player.player_id && number(player.minutes_played) > 0);
    if (!players.length) return null;
    const filters = { qualified: true, positionGroup: "all", inferredPosition: "all", team: "all", minMinutes: 90, minShots: 3, minGames: 1 };
    const comparisonHost = node("div"), positionHost = node("div"), rankingHost = node("div"), creationHost = node("div");
    const tableHost = node("div");
    const count = node("span");
    const qualifiedToggle = attachTabListKeyNav(node("div", { class: "segmented-control overview-qualified-toggle", role: "tablist", "aria-label": "Elegibilidade dos jogadores" }, [
      node("button", { type: "button", text: "Qualificados", role: "tab", title: "Qualificados: jogadores acima dos mínimos de minutos, finalizações e jogos definidos nos filtros abaixo.", onclick: () => { filters.qualified = true; drawToggle(); draw(); } }),
      node("button", { type: "button", text: "Todos", role: "tab", onclick: () => { filters.qualified = false; drawToggle(); draw(); } }),
    ]));
    function drawToggle() {
      qualifiedToggle.querySelectorAll("button").forEach((button, index) => {
        const selected = (index === 0) === filters.qualified;
        button.classList.toggle("is-active", selected);
        button.setAttribute("aria-selected", String(selected));
      });
      numberInputs.forEach(input => { input.disabled = !filters.qualified; });
    }
    const numberInputs = [];
    const controls = node("div", { class: "overview-filter-grid" }, [
      overviewSelect("Posição (grupo amplo)", "positionGroup", [["all", "Todos"], ...(data.filters?.position_groups || []).map(value => [value, value])]),
      overviewSelect("Posição (detalhada)", "inferredPosition", [["all", "Todas"], ...(data.filters?.inferred_positions || []).map(value => [value, value])]),
      overviewSelect("Seleção", "team", [["all", "Todas"], ...(data.filters?.teams || []).map(value => [value, displayTeamName(value)])]),
      overviewNumber("Minutos mínimos", "minMinutes", 30), overviewNumber("Finalizações mínimas", "minShots", 1), overviewNumber("Jogos mínimos", "minGames", 1),
    ]);
    function overviewSelect(labelText, key, options) {
      const select = node("select", { onchange: event => { filters[key] = event.target.value; draw(); } }, options.map(([value, optionLabel]) => node("option", { value, text: optionLabel })));
      return node("label", {}, [node("span", { text: labelText }), select]);
    }
    function overviewNumber(labelText, key, step) {
      const input = node("input", { type: "number", min: 0, step, value: filters[key], oninput: event => { filters[key] = Math.max(0, number(event.target.value) || 0); draw(); } });
      numberInputs.push(input);
      return node("label", {}, [node("span", { text: labelText }), input]);
    }
    function filtered() {
      return players.filter(player => {
        if (filters.positionGroup !== "all" && player.api_position_group !== filters.positionGroup) return false;
        if (filters.inferredPosition !== "all" && resolvedPlayerPosition(player) !== filters.inferredPosition) return false;
        if (filters.team !== "all" && player.team_name !== filters.team) return false;
        if (!filters.qualified) return true;
        if (number(player.minutes_played) < filters.minMinutes) return false;
        if (number(player.games) < filters.minGames) return false;
        // Shot-volume eligibility doesn't apply to goalkeepers — they rarely take shots at all,
        // and the "Qualificados" default would silently drop the whole position otherwise.
        const isGoalkeeper = positionLabel(player.position) === "GOL";
        if (!isGoalkeeper && number(player.shots) < filters.minShots) return false;
        return true;
      });
    }
    function draw() {
      const rows = filtered(); count.textContent = `${rows.length} jogadores`;
      comparisonHost.replaceChildren(playerComparisonMap(rows, player => goToProfile("player", player.player_id)));
      positionHost.replaceChildren(playerPositionDistribution(rows));
      creationHost.replaceChildren(playerCreationProfile(rows) || emptyState("Perfil de criação indisponível", "Não há dados de criação suficientes neste recorte."));
      tableHost.replaceChildren(playerOverviewTable(rows, { onSelect: player => goToProfile("player", player.player_id) }));
      const rankings = playerRankingPanels(rows);
      rankingHost.replaceChildren(rankings || emptyState("Sem rankings neste recorte", "Ajuste os filtros para encontrar jogadores elegíveis."));
    }
    const shotBreakdown = playerShotBreakdown(data.shot_breakdowns || {});
    const highlights = playerEditionHighlights(players);
    const root = node("div", { class: "player-overview-experience" }, [
      compactAnalysisSummary([["Jogadores", data.summary?.players], ["Gols", data.summary?.goals], ["Finalizações", data.summary?.shots], ["xG total", data.summary?.xg]]),
      node("div", { class: "overview-filter-toolbar" }, [qualifiedToggle, controls]),
      highlights ? section("Destaques da edição", "Nomes que definem o recorte", highlights) : null,
      section("Mapa de comparação", count, comparisonHost),
      section("Produção por posição", "Distribuição ofensiva e defensiva entre as funções", positionHost),
      shotBreakdown ? section("Perfil das finalizações", "Recorte fixo: toda a Copa — os filtros acima não se aplicam a este bloco", shotBreakdown) : null,
      section("Perfil de criação", "Passes para finalização e cruzamentos na competição", creationHost),
      section("Rankings de jogadores", "Top 5 · escolha uma categoria", rankingHost),
      section("Lista de jogadores", "Clique em uma linha para abrir o Perfil", analysisTableDisclosure("Tabela completa de jogadores", tableHost)),
    ].filter(Boolean));
    drawToggle();
    draw();
    return root;
  }

  function teamEditionHighlights(teams) {
    const pick = (metric, ascending = false) => [...teams]
      .filter(team => number(team[metric]) !== null && number(team.played) > 0)
      .sort((left, right) => ascending ? number(left[metric]) - number(right[metric]) : number(right[metric]) - number(left[metric]))[0];
    const dominant = pick("xg_difference"), attack = pick("goals_for"), defense = pick("xga_per_game", true), efficient = pick("goals_minus_xg");
    const highlights = [
      dominant ? { kicker: "Mais dominante", team: dominant, value: `${signedStandingValue(dominant.xg_difference)} saldo de xG`, detail: `${formatValue(dominant.xg_per_game)} xG criado por jogo` } : null,
      attack ? { kicker: "Melhor ataque", team: attack, value: `${formatValue(attack.goals_for)} gols`, detail: `${formatValue(attack.goals_per_game)} por jogo` } : null,
      defense ? { kicker: "Defesa mais sólida", team: defense, value: `${formatValue(defense.xga_per_game)} xG cedido/jogo`, detail: `${formatValue(defense.goals_against)} gols sofridos` } : null,
      efficient ? { kicker: "Mais eficiente", team: efficient, value: `${signedStandingValue(efficient.goals_minus_xg)} gols - xG`, detail: `${formatValue(efficient.conversion)}% de conversão` } : null,
    ].filter(Boolean);
    const formulas = {
      "Mais dominante": "Fórmula: saldo de xG (xG criado − xG cedido).",
      "Melhor ataque": "Fórmula: gols marcados na Copa.",
      "Defesa mais sólida": "Fórmula: xG cedido por jogo (menor é melhor).",
      "Mais eficiente": "Fórmula: gols − xG (conversão acima do esperado).",
    };
    return node("div", { class: "team-editorial-highlights" }, highlights.map(({ kicker, team, value, detail }) => node("button", {
      type: "button", title: formulas[kicker] || null, onclick: () => goToProfile("team", team.team_id),
    }, [node("small", { text: kicker }), node("strong", {}, [flagNode(team), node("span", { text: teamName(team) })]), node("b", { text: value }), node("span", { text: detail })])));
  }

  function teamComparisonInsights(teams, mode) {
    const pick = (metric, ascending = false) => [...teams]
      .filter(team => number(team[metric]) !== null && number(team.played) > 0)
      .sort((left, right) => ascending ? number(left[metric]) - number(right[metric]) : number(right[metric]) - number(left[metric]))[0];
    const modes = {
      dominance: [
        ["Mais dominante", pick("xg_difference"), "xg_difference", "saldo de xG", true],
        ["Melhor defesa por xG", pick("xga_per_game", true), "xga_per_game", "xG cedido/jogo"],
        ["Ataque mais produtivo", pick("xg_per_game"), "xg_per_game", "xG/jogo"],
        ["Mais exposta", pick("xga_per_game"), "xga_per_game", "xG cedido/jogo"],
      ],
      efficiency: [
        ["Mais acima do xG", pick("goals_minus_xg"), "goals_minus_xg", "gols - xG", true],
        ["Mais abaixo do xG", pick("goals_minus_xg", true), "goals_minus_xg", "gols - xG", true],
        ["Mais gols", pick("goals_for"), "goals_for", "gols"],
        ["Maior conversão", pick("conversion"), "conversion", "% conversão"],
      ],
      volume: [
        ["Maior saldo", pick("shot_difference"), "shot_difference", "finalizações", true],
        ["Maior volume", pick("shots_per_game"), "shots_per_game", "chutes/jogo"],
        ["Menos pressionada", pick("shots_against_per_game", true), "shots_against_per_game", "sofridas/jogo"],
        ["Mais pressionada", pick("shots_against_per_game"), "shots_against_per_game", "sofridas/jogo"],
      ],
      possession: [
        ["Maior posse", pick("average_possession"), "average_possession", "% de posse"],
        ["Passe mais preciso", pick("pass_accuracy"), "pass_accuracy", "% precisão"],
        ["Mais passes certos", pick("accurate_passes"), "accurate_passes", "passes certos"],
      ],
    };
    const rows = (modes[mode] || []).filter(([, team]) => team);
    return node("aside", { class: "team-map-insights" }, [node("h3", { text: "Destaques do mapa" }), ...rows.map(([labelText, team, metric, unit, signed]) => {
      const value = number(team[metric]);
      return node("button", { type: "button", onclick: () => goToProfile("team", team.team_id) }, [node("small", { text: labelText }), node("strong", {}, [flagNode(team), node("span", { text: teamName(team) })]), node("b", { text: `${signed && value > 0 ? "+" : ""}${formatValue(value)} ${unit}` })]);
    })]);
  }

  function teamComparisonMap(teams, onSelect) {
    const modes = [
      { id: "dominance", label: "xG criado × cedido", description: "Criação alta e concessão baixa indicam maior domínio.", render: () => teamComparisonScatter(teams, onSelect) },
      { id: "efficiency", label: "Gols × xG", description: "Mostra quem converteu acima ou abaixo do esperado.", render: () => teamSecondaryScatterPlot(teams, "efficiency", onSelect) },
      { id: "volume", label: "Finalizações feitas × sofridas", description: "Compara pressão criada e concedida por jogo.", render: () => teamSecondaryScatterPlot(teams, "volume", onSelect) },
      ...(teams.some(team => number(team.average_possession) !== null && number(team.pass_accuracy) !== null) ? [{ id: "possession", label: "Posse × precisão", description: "Relaciona controle da bola e segurança na circulação.", render: () => teamSecondaryScatterPlot(teams, "possession", onSelect) }] : []),
    ];
    let active = modes[0];
    const chart = node("div", { class: "team-comparison-chart" }), insights = node("div"), description = node("p");
    const tabs = attachTabListKeyNav(node("div", { class: "segmented-control team-comparison-switch", role: "tablist", "aria-label": "Métrica do mapa de comparação" }));
    const draw = () => {
      tabs.querySelectorAll("button").forEach(button => { const selected = button.dataset.mode === active.id; button.classList.toggle("is-active", selected); button.setAttribute("aria-selected", String(selected)); });
      description.textContent = active.description;
      chart.replaceChildren(active.render());
      insights.replaceChildren(teamComparisonInsights(teams, active.id));
    };
    tabs.replaceChildren(...modes.map(mode => node("button", { type: "button", role: "tab", text: mode.label, "data-mode": mode.id, onclick: () => { active = mode; draw(); } })));
    draw();
    return node("div", { class: "team-comparison-map" }, [node("div", { class: "team-comparison-toolbar" }, [tabs, description]), node("div", { class: "team-comparison-layout" }, [chart, insights])]);
  }

  function teamProductionOverview(teams) {
    const definitions = [
      { id: "goals_per_game", label: "Gols por jogo", unit: "gols/jogo" },
      { id: "xg_per_game", label: "xG criado por jogo", unit: "xG/jogo" },
      { id: "shots_per_game", label: "Finalizações por jogo", unit: "chutes/jogo" },
      { id: "shots_on_target", label: "Finalizações no alvo", unit: "no alvo", value: team => number(team.shots_on_target) / Math.max(1, number(team.played)) },
      { id: "xga_per_game", label: "Menor xG cedido por jogo", unit: "xG/jogo", ascending: true },
      { id: "shots_against_per_game", label: "Menos finalizações sofridas", unit: "sofridas/jogo", ascending: true },
      { id: "xg_difference", label: "Saldo de xG", unit: "xG", signed: true },
    ];
    const select = node("select", { "aria-label": "Métrica de produção coletiva" }, definitions.map(definition => node("option", { value: definition.id, text: definition.label })));
    const host = node("div", { class: "team-production-bars" }), note = node("span");
    const draw = () => {
      const definition = definitions.find(item => item.id === select.value) || definitions[0];
      const rows = teams.map(team => ({ team, value: definition.value ? definition.value(team) : number(team[definition.id]) })).filter(row => row.value !== null && Number.isFinite(row.value)).sort((left, right) => {
        const diff = definition.ascending ? left.value - right.value : right.value - left.value;
        return diff !== 0 ? diff : rankingTieBreakName(left.team).localeCompare(rankingTieBreakName(right.team), "pt-BR");
      }).slice(0, 8);
      const max = Math.max(...rows.map(row => Math.abs(row.value)), 1);
      note.textContent = definition.ascending ? "Menor é melhor" : "Maior é melhor";
      host.replaceChildren(...rows.map(({ team, value }, index) => node("button", { type: "button", onclick: () => goToProfile("team", team.team_id) }, [
        node("span", { class: "home-rank", text: index + 1 }), homeRankingEntity(team, "team"),
        node("span", { class: "team-production-track" }, node("i", { style: `width:${Math.max(3, Math.abs(value) / max * 100)}%` })),
        node("b", { text: `${definition.signed && value > 0 ? "+" : ""}${formatValue(value)} ${definition.unit}` }),
      ])));
    };
    select.onchange = draw; draw();
    return node("div", { class: "team-production-overview" }, [node("div", { class: "team-production-controls" }, [node("label", {}, [node("span", { text: "Métrica" }), select]), note]), host]);
  }

  function teamCollectiveProfile(breakdowns) {
    let mode = "goals";
    const host = node("div", { class: "team-collective-panels" });
    const tabs = attachTabListKeyNav(node("div", { class: "segmented-control team-collective-switch", role: "tablist", "aria-label": "Medida do perfil coletivo" }));
    const definitions = [["body_part", "Parte do corpo", BODY_PART_LABELS], ["shot_type", "Situação da finalização", SHOT_TYPE_LABELS]];
    const draw = () => {
      tabs.querySelectorAll("button").forEach(button => { const selected = button.dataset.mode === mode; button.classList.toggle("is-active", selected); button.setAttribute("aria-selected", String(selected)); });
      host.replaceChildren(...definitions.map(([key, title, labels]) => {
        const rows = (breakdowns?.[key] || []).map(item => ({ ...item, amount: number(item[mode]) || 0 }));
        return node("article", { class: "team-collective-panel" }, [
          node("h3", { text: title }),
          breakdownBars(rows, "amount", { name: item => labels[String(item.label).toLowerCase()] || label(item.label) }),
        ]);
      }));
    };
    tabs.replaceChildren(...[["goals", "Gols"], ["shots", "Finalizações"]].map(([key, labelText]) => node("button", { type: "button", role: "tab", text: labelText, "data-mode": key, onclick: () => { mode = key; draw(); } })));
    draw();
    return node("div", { class: "team-collective-profile" }, [tabs, host]);
  }

  function teamRankingExplorer(teams) {
    const category = definition => ({ Ataque: "Ataque", Defesa: "Defesa", Domínio: "Eficiência", "Posse e passe": "Controle", "Sem bola": "Defesa", Disciplina: "Disciplina" }[definition.category] || definition.category);
    const definitions = teamMetricDefinitions();
    const categories = ["Ataque", "Defesa", "Eficiência", "Controle", "Disciplina"].filter(name => definitions.some(definition => category(definition) === name && analysisMetricRows(teams, definition).length));
    if (!categories.length) return null;
    let activeCategory = categories[0], activeMetric = null;
    const tabs = attachTabListKeyNav(node("div", { class: "segmented-control analysis-ranking-tabs", role: "tablist", "aria-label": "Categorias de ranking" })), select = node("select", { "aria-label": "Métrica do ranking" }), host = node("div", { class: "team-ranking-single" });
    const available = () => definitions.filter(definition => category(definition) === activeCategory && analysisMetricRows(teams, definition).length);
    const drawMetric = () => { const rows = available(), definition = rows.find(item => item.id === activeMetric) || rows[0]; if (!definition) return; activeMetric = definition.id; select.replaceChildren(...rows.map(item => node("option", { value: item.id, text: item.title }))); select.value = activeMetric; host.replaceChildren(analysisRankingPanels(teams, [definition], "team")); };
    const drawCategory = () => { tabs.querySelectorAll("button").forEach(button => { const selected = button.dataset.category === activeCategory; button.classList.toggle("is-active", selected); button.setAttribute("aria-selected", String(selected)); }); activeMetric = null; drawMetric(); };
    tabs.replaceChildren(...categories.map(name => node("button", { type: "button", role: "tab", text: name, "data-category": name, onclick: () => { activeCategory = name; drawCategory(); } })));
    select.onchange = event => { activeMetric = event.target.value; drawMetric(); }; drawCategory();
    return node("div", { class: "analysis-ranking-explorer team-ranking-explorer" }, [node("div", { class: "team-ranking-controls" }, [tabs, node("label", {}, [node("span", { text: "Métrica" }), select])]), host]);
  }

  const STAGE_FILTER_ORDER = ["Fase de grupos", "Fase de 32", "Oitavas", "Quartas", "Semifinais", "Disputa de 3º lugar", "Final"];

  function teamAnalysisExperience(data) {
    const teams = (data.items || []).filter(team => team.team_id);
    if (!teams.length) return null;
    const filters = { group: "all", status: "all", stage: "all", minGames: 1 };
    const comparisonHost = node("div"), productionHost = node("div"), rankingHost = node("div"), count = node("span");
    const groups = [...new Set(teams.map(team => team.group_name).filter(Boolean))].sort();
    const statuses = [...new Set(teams.map(team => team.classification_status || team.status).filter(Boolean))].sort();
    const stages = [...new Set(teams.flatMap(team => team.stages || []))].sort((left, right) => STAGE_FILTER_ORDER.indexOf(left) - STAGE_FILTER_ORDER.indexOf(right));
    const controls = node("div", { class: "overview-filter-grid team-overview-filters" }, [
      node("label", {}, [node("span", { text: "Grupo" }), node("select", { onchange: event => { filters.group = event.target.value; draw(); } }, [node("option", { value: "all", text: "Todos" }), ...groups.map(group => node("option", { value: group, text: `Grupo ${group}` }))])]),
      node("label", {}, [node("span", { text: "Fase" }), node("select", { onchange: event => { filters.stage = event.target.value; draw(); } }, [node("option", { value: "all", text: "Todas" }), ...stages.map(stage => node("option", { value: stage, text: stage }))])]),
      node("label", {}, [node("span", { text: "Status na competição" }), node("select", { onchange: event => { filters.status = event.target.value; draw(); } }, [node("option", { value: "all", text: "Todos" }), ...statuses.map(status => node("option", { value: status, text: status }))])]),
      node("label", {}, [node("span", { text: "Jogos mínimos" }), node("input", { type: "number", min: 0, step: 1, value: filters.minGames, oninput: event => { filters.minGames = Math.max(0, number(event.target.value) || 0); draw(); } })]),
    ]);
    function filtered() { return teams.filter(team => (filters.group === "all" || team.group_name === filters.group) && (filters.status === "all" || (team.classification_status || team.status) === filters.status) && (filters.stage === "all" || (team.stages || []).includes(filters.stage)) && number(team.played) >= filters.minGames); }
    function draw() {
      const rows = filtered(); count.textContent = `${rows.length} seleções`;
      comparisonHost.replaceChildren(teamComparisonMap(rows, team => goToProfile("team", team.team_id)));
      productionHost.replaceChildren(teamProductionOverview(rows));
      rankingHost.replaceChildren(teamRankingExplorer(rows) || emptyState("Sem rankings neste recorte", "Ajuste os filtros para encontrar seleções elegíveis."));
    }
    const breakdowns = data.shot_breakdowns || {};
    const hasBreakdowns = Object.values(breakdowns).some(rows => rows?.length);
    const root = node("div", { class: "team-analysis-experience" }, [
      compactAnalysisSummary([["Seleções", data.summary?.teams], ["Gols", data.summary?.goals], ["xG total", data.summary?.xg], ["Gols por jogo", data.summary?.goals_per_match]]),
      controls,
      section("Destaques da edição", "Quem está definindo a Copa", teamEditionHighlights(teams)),
      section("Mapa de comparação", count, comparisonHost),
      section("Produção ofensiva e defensiva", "Métricas por jogo quando aplicável", productionHost),
      hasBreakdowns ? section("Perfil coletivo", "Recorte fixo: toda a Copa — os filtros acima não se aplicam a este bloco", teamCollectiveProfile(breakdowns)) : null,
      section("Rankings de seleções", "Top 5 · escolha uma métrica", rankingHost),
    ]);
    draw();
    return root;
  }

  function teamComparisonScatter(teams, onSelect) {
    const clean = teams.filter(team => number(team.xg) !== null && number(team.xga) !== null);
    if (!clean.length) return emptyState("Comparação indisponível", "Não há xG criado e cedido suficientes.");
    const width = 720, height = 410, pad = 48, maxX = Math.max(...clean.map(team => number(team.xg)), 1), maxY = Math.max(...clean.map(team => number(team.xga)), 1);
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "xG criado por xG cedido das seleções" });
    for (let tick = 0; tick <= 4; tick += 1) {
      const x = pad + (width - pad * 2) * tick / 4, y = height - pad - (height - pad * 2) * tick / 4;
      svg.append(svgNode("line", { x1: x, y1: pad, x2: x, y2: height - pad, class: "chart-gridline" }), svgNode("line", { x1: pad, y1: y, x2: width - pad, y2: y, class: "chart-gridline" }));
    }
    const highlighted = new Set([
      [...clean].sort((left, right) => number(right.xg_difference) - number(left.xg_difference))[0]?.team_id,
      [...clean].sort((left, right) => number(right.xg) - number(left.xg))[0]?.team_id,
      [...clean].sort((left, right) => number(left.xga) - number(right.xga))[0]?.team_id,
    ].filter(Boolean));
    // Quadrantes interpretativos nas medianas: a leitura vem escrita no gráfico,
    // sem exigir interpretação técnica dos eixos.
    const medianX = [...clean].map(team => number(team.xg)).sort((a, b) => a - b)[Math.floor(clean.length / 2)];
    const medianY = [...clean].map(team => number(team.xga)).sort((a, b) => a - b)[Math.floor(clean.length / 2)];
    const xMid = pad + medianX / maxX * (width - pad * 2);
    const yMid = height - pad - medianY / maxY * (height - pad * 2);
    svg.append(
      svgNode("line", { x1: xMid, y1: pad, x2: xMid, y2: height - pad, class: "scatter-quadrant-line" }),
      svgNode("line", { x1: pad, y1: yMid, x2: width - pad, y2: yMid, class: "scatter-quadrant-line" }),
      svgNode("text", { x: width - pad - 6, y: height - pad - 8, class: "scatter-quadrant-label", "text-anchor": "end" }, "Dominantes"),
      svgNode("text", { x: width - pad - 6, y: pad + 14, class: "scatter-quadrant-label", "text-anchor": "end" }, "Criam muito, mas cedem muito"),
      svgNode("text", { x: pad + 6, y: height - pad - 8, class: "scatter-quadrant-label" }, "Sólidas, mas pouco produtivas"),
      svgNode("text", { x: pad + 6, y: pad + 14, class: "scatter-quadrant-label" }, "Em dificuldade"),
    );
    clean.forEach(team => {
      const cx = pad + number(team.xg) / maxX * (width - pad * 2), cy = height - pad - number(team.xga) / maxY * (height - pad * 2);
      const tooltip = `${teamName(team)} · ${formatValue(team.played)} jogos · ${formatValue(team.goals_for)} gols marcados · ${formatValue(team.goals_against)} sofridos · ${formatValue(team.xg)} xG criado · ${formatValue(team.xga)} xG cedido · saldo ${signedStandingValue(team.xg_difference)} · ${formatValue(team.shots_per_game)} finalizações por jogo`;
      svg.append(scatterEntityMarker(team, { cx, cy, kind: "team", tooltip, onSelect }));
      if (highlighted.has(team.team_id)) svg.append(svgNode("text", { x: cx + 10, y: cy - 9, class: "team-scatter-label" }, teamName(team)));
    });
    svg.append(svgNode("text", { x: width / 2, y: height - 4, class: "chart-axis-title", "text-anchor": "middle" }, "xG criado"), svgNode("text", { x: 14, y: height / 2, class: "chart-axis-title", transform: `rotate(-90 14 ${height / 2})`, "text-anchor": "middle" }, "xG cedido"));
    return node("div", { class: "svg-chart" }, svg);
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
    const dense = clean.length > 60;
    const standouts = new Set([...clean].sort((a, b) => (b.x + b.y) - (a.x + a.y)).slice(0, 6).map(point => point.item.player_id));
    clean.forEach(point => {
      const selected = point.item.player_id === selectedId;
      const tooltip = `${personName(point.item)} · ${teamName(point.item)} · ${resolvedPlayerPosition(point.item)} · ${formatValue(point.y)} gols · ${formatValue(point.x)} xG · ${formatValue(point.item.minutes_played)} min · ${formatValue(point.item.shots)} finalizações`;
      svg.append(scatterEntityMarker(point.item, {
        cx: xAt(point.x), cy: yAt(point.y), kind: "player", selected, tooltip, onSelect, dense,
        plain: !standouts.has(point.item.player_id),
      }));
    });
    svg.append(svgNode("text", { x: width / 2, y: height - 2, class: "chart-axis-title", "text-anchor": "middle" }, "xG"));
    svg.append(svgNode("text", { x: 13, y: height / 2, class: "chart-axis-title", transform: `rotate(-90 13 ${height / 2})`, "text-anchor": "middle" }, "Gols"));
    return node("div", { class: "svg-chart player-scatter-chart" }, svg);
  }

  function analysisScatterPlot(rows, config) {
    const clean = rows.map(item => ({ item, x: number(config.xValue(item)), y: number(config.yValue(item)) })).filter(point => point.x !== null && point.y !== null);
    if (!clean.length) return emptyState("Comparação indisponível", "Não há dados suficientes para este gráfico.");
    const width = 720, height = 410, pad = 48;
    const maxX = Math.max(...clean.map(point => point.x), 1), maxY = Math.max(...clean.map(point => point.y), 1);
    const xAt = value => pad + value / maxX * (width - pad * 2);
    const yAt = value => height - pad - value / maxY * (height - pad * 2);
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": config.ariaLabel });
    for (let tick = 0; tick <= 4; tick += 1) {
      const x = pad + (width - pad * 2) * tick / 4, y = height - pad - (height - pad * 2) * tick / 4;
      svg.append(
        svgNode("line", { x1: x, y1: pad, x2: x, y2: height - pad, class: "chart-gridline" }),
        svgNode("line", { x1: pad, y1: y, x2: width - pad, y2: y, class: "chart-gridline" }),
        svgNode("text", { x, y: height - 17, class: "chart-axis", "text-anchor": "middle" }, formatValue(maxX * tick / 4)),
        svgNode("text", { x: 34, y: y + 4, class: "chart-axis", "text-anchor": "end" }, formatValue(maxY * tick / 4)),
      );
    }
    if (config.reference) {
      const referenceMax = Math.min(maxX, maxY);
      svg.append(svgNode("line", { x1: xAt(0), y1: yAt(0), x2: xAt(referenceMax), y2: yAt(referenceMax), class: "scatter-reference-line" }));
    } else if (config.quadrants) {
      const medianX = [...clean].sort((a, b) => a.x - b.x)[Math.floor(clean.length / 2)].x;
      const medianY = [...clean].sort((a, b) => a.y - b.y)[Math.floor(clean.length / 2)].y;
      svg.append(
        svgNode("line", { x1: xAt(medianX), y1: pad, x2: xAt(medianX), y2: height - pad, class: "scatter-quadrant-line" }),
        svgNode("line", { x1: pad, y1: yAt(medianY), x2: width - pad, y2: yAt(medianY), class: "scatter-quadrant-line" }),
      );
    }
    const dense = clean.length > 60;
    const scaleX = value => (Number.isFinite(value) ? value : 0);
    const standouts = config.entity === "player"
      ? new Set([...clean].sort((a, b) => (scaleX(b.x) + scaleX(b.y)) - (scaleX(a.x) + scaleX(a.y))).slice(0, 6).map(point => point.item.player_id))
      : null;
    clean.forEach(point => {
      const tooltip = config.tooltip(point.item, point.x, point.y);
      svg.append(scatterEntityMarker(point.item, {
        cx: xAt(point.x), cy: yAt(point.y), kind: config.entity, tooltip, onSelect: config.onSelect, dense,
        plain: standouts ? !standouts.has(point.item.player_id) : false,
      }));
    });
    svg.append(
      svgNode("text", { x: width / 2, y: height - 2, class: "chart-axis-title", "text-anchor": "middle" }, config.xLabel),
      svgNode("text", { x: 13, y: height / 2, class: "chart-axis-title", transform: `rotate(-90 13 ${height / 2})`, "text-anchor": "middle" }, config.yLabel),
    );
    return node("div", { class: "svg-chart analytical-scatter-chart" }, svg);
  }

  function playerDuelsDisputed(player) {
    return (number(player.duels_won) || 0) + (number(player.duels_lost) || 0);
  }

  const PLAYER_SCATTER_CONFIGS = {
    creation: {
      xValue: player => player.xg, yValue: player => player.xa,
      xLabel: "xG", yLabel: "xA",
      ariaLabel: "Dispersão de xG por xA dos jogadores",
      tooltip: player => `${personName(player)} · ${displayTeamName(player.team_name)} · ${resolvedPlayerPosition(player)} · ${formatValue(player.xg)} xG · ${formatValue(player.xa)} xA · ${formatValue(player.goals)} gols · ${formatValue(player.assists)} assistências · ${formatValue(player.minutes_played)} min`,
    },
    volume: {
      xValue: player => player.shots, yValue: player => player.xg,
      xLabel: "Finalizações", yLabel: "xG",
      ariaLabel: "Dispersão de finalizações por xG dos jogadores",
      tooltip: player => `${personName(player)} · ${displayTeamName(player.team_name)} · ${resolvedPlayerPosition(player)} · ${formatValue(player.shots)} finalizações · ${formatValue(player.xg)} xG · ${formatValue(player.minutes_played)} min`,
    },
    shot_efficiency: {
      xValue: player => player.shots, yValue: player => player.shot_conversion,
      xLabel: "Finalizações", yLabel: "Conversão (%)",
      ariaLabel: "Dispersão de finalizações por percentual de conversão dos jogadores",
      tooltip: player => `${personName(player)} · ${displayTeamName(player.team_name)} · ${resolvedPlayerPosition(player)} · ${formatValue(player.shots)} finalizações · ${formatValue(player.shot_conversion)}% conversão · ${formatValue(player.goals)} gols · ${formatValue(player.minutes_played)} min`,
    },
    duels: {
      xValue: playerDuelsDisputed,
      yValue: player => { const disputed = playerDuelsDisputed(player); return disputed > 0 ? (number(player.duels_won) || 0) / disputed * 100 : null; },
      xLabel: "Duelos disputados", yLabel: "% de duelos ganhos",
      ariaLabel: "Dispersão de duelos disputados por percentual de duelos ganhos dos jogadores",
      tooltip: player => `${personName(player)} · ${displayTeamName(player.team_name)} · ${resolvedPlayerPosition(player)} · ${formatValue(player.duels_won)} ganhos de ${formatValue(playerDuelsDisputed(player))} disputados · ${formatValue(player.minutes_played)} min`,
    },
    per90: {
      xValue: player => player.goals_per_90, yValue: player => player.xg_per_90,
      xLabel: "Gols por 90", yLabel: "xG por 90",
      ariaLabel: "Dispersão de gols por 90 por xG por 90 dos jogadores",
      tooltip: player => `${personName(player)} · ${displayTeamName(player.team_name)} · ${resolvedPlayerPosition(player)} · ${formatValue(player.goals_per_90)} gols/90 · ${formatValue(player.xg_per_90)} xG/90 · ${formatValue(player.minutes_played)} min`,
    },
  };

  function playerSecondaryScatterPlot(rows, mode, onSelect) {
    const config = PLAYER_SCATTER_CONFIGS[mode] || PLAYER_SCATTER_CONFIGS.creation;
    return analysisScatterPlot(rows, { entity: "player", onSelect, quadrants: true, ...config });
  }

  function teamSecondaryScatterPlot(rows, mode, onSelect) {
    const efficiency = mode === "efficiency", possession = mode === "possession";
    return analysisScatterPlot(rows, {
      entity: "team", onSelect, reference: efficiency, quadrants: !efficiency,
      xValue: team => efficiency ? team.xg : possession ? team.average_possession : team.shots_per_game,
      yValue: team => efficiency ? team.goals_for : possession ? team.pass_accuracy : team.shots_against_per_game,
      xLabel: efficiency ? "xG" : possession ? "Posse média (%)" : "Finalizações por jogo",
      yLabel: efficiency ? "Gols" : possession ? "Precisão de passe (%)" : "Finalizações sofridas por jogo",
      ariaLabel: efficiency ? "Dispersão de gols por xG das seleções" : possession ? "Dispersão de posse por precisão de passe das seleções" : "Dispersão de finalizações feitas e sofridas das seleções",
      tooltip: team => `${teamName(team)} · ${formatValue(team.played)} jogos · ${formatValue(team.goals_for)} gols · ${formatValue(team.xg)} xG · ${formatValue(team.xga)} xG cedido · saldo ${signedStandingValue(team.xg_difference)} · ${formatValue(team.shots)} finalizações`,
    });
  }

  function playerPositionDistribution(rows) {
    const metrics = [
      ["goals", "Gols"], ["xg", "xG"], ["shots", "Finalizações"], ["assists", "Assistências"],
      ["tackles", "Desarmes"], ["interceptions", "Interceptações"], ["clearances", "Cortes"], ["defensive_actions", "Ações defensivas"],
    ];
    const host = node("div");
    const select = node("select", { "aria-label": "Métrica por posição" }, metrics.map(([value, labelText]) => node("option", { value, text: labelText })));
    const draw = () => {
      const metric = select.value || "goals";
      const grouped = new Map();
      const samples = new Map();
      rows.forEach(player => {
        const key = resolvedPlayerPosition(player);
        grouped.set(key, (grouped.get(key) || 0) + (number(player[metric]) || 0));
        samples.set(key, (samples.get(key) || 0) + 1);
      });
      const values = [...grouped].map(([labelText, value]) => ({ label: `${labelText} (${samples.get(labelText)})`, value: Math.round(value * 100) / 100 })).sort((a, b) => b.value - a.value);
      host.replaceChildren(horizontalBars(values, "value", { name: item => item.label, limit: 8 }));
    };
    select.onchange = draw; draw();
    return node("div", { class: "player-position-production" }, [
      node("label", {}, [node("span", { text: "Métrica" }), select]),
      host,
    ]);
  }


  function breakdownBars(rows, valueKey, { name = item => item.label } = {}) {
    const clean = rows.map(item => ({ item, value: number(item[valueKey]) || 0 })).filter(entry => entry.value > 0).sort((a, b) => b.value - a.value);
    if (!clean.length) return emptyState("Sem dados neste recorte");
    const total = clean.reduce((sum, entry) => sum + entry.value, 0);
    const max = clean[0].value;
    return node("div", { class: "player-distribution-bars breakdown-bars" }, clean.map(({ item, value }) => {
      const pct = value / total * 100;
      return node("div", { class: "player-distribution-row", title: `${name(item)}: ${formatValue(value)} (${formatValue(Math.round(pct * 10) / 10)}%)` }, [
        node("span", { text: name(item) }),
        node("span", { class: "player-distribution-track" }, [node("span", { style: `width:${value / max * 100}%` })]),
        node("strong", { text: formatValue(value) }),
        node("small", { text: `${formatValue(Math.round(pct * 10) / 10)}%` }),
      ]);
    }));
  }

  function playerShotBreakdown(breakdowns) {
    const panels = [["body_part", "Gols por parte do corpo", BODY_PART_LABELS], ["shot_type", "Gols por situação", SHOT_TYPE_LABELS]]
      .filter(([key]) => breakdowns?.[key]?.length)
      .map(([key, title, labels]) => node("article", { class: "analysis-chart-panel" }, [
        node("header", {}, [node("span", {}, [node("h3", { text: title }), node("p", { text: "Finalizações convertidas na competição." })])]),
        breakdownBars(breakdowns[key], "goals", { name: item => labels[String(item.label).toLowerCase()] || label(item.label) }),
      ]));
    return panels.length ? node("div", { class: "analysis-chart-grid" }, panels) : null;
  }

  function playerCreationProfile(rows) {
    const panels = [
      ["key_passes", "Passes para finalização", "passes"],
      ["accurate_crosses", "Cruzamentos certos", "cruzamentos"],
    ].map(([metric, title, unit]) => {
      const eligible = rows
        .filter(player => number(player[metric]) > 0)
        .sort((left, right) => number(right[metric]) - number(left[metric]));
      if (!eligible.length) return null;
      return node("article", { class: "analysis-chart-panel" }, [
        node("header", {}, [node("span", {}, [node("h3", { text: title }), node("p", { text: "Top jogadores na competição." })])]),
        horizontalBars(eligible, metric, { name: personName, limit: 8, unit: ` ${unit}` }),
      ]);
    }).filter(Boolean);
    return panels.length ? node("div", { class: "analysis-chart-grid" }, panels) : null;
  }

  function analysisTableDisclosure(labelText, tableHost) {
    return node("details", { class: "analysis-table-disclosure" }, [node("summary", {}, [node("span", { text: labelText }), node("strong", { text: "Abrir tabela" })]), tableHost]);
  }

  function playerOverviewTable(rows, { selectedId = null, onSelect = null } = {}) {
    let sort = { key: "minutes_played", direction: "desc" };
    const columns = [
      { key: "player_name", label: "Jogador", value: player => personName(player), render: player => node("span", { class: "players-table-player" }, [flagNode(player), node("strong", { text: personName(player) })]) },
      { key: "team_name", label: "Seleção", value: player => displayTeamName(player.team_name) },
      { key: "position", label: "Pos.", value: player => resolvedPlayerPosition(player, true) },
      { key: "minutes_played", label: "Min.", value: player => number(player.minutes_played) },
      { key: "goals", label: "Gols", value: player => number(player.goals) },
      { key: "assists", label: "Assist.", value: player => number(player.assists) },
      { key: "xg", label: "xG", value: player => number(player.xg) },
      { key: "xa", label: "xA", value: player => number(player.xa) },
      { key: "shots", label: "Finalizações", value: player => number(player.shots) },
      { key: "defensive_actions", label: "Ações defensivas", value: player => number(player.defensive_actions) },
      { key: "rating", label: "Rating", value: player => number(player.rating) },
    ];
    const thead = node("thead");
    const tbody = node("tbody");

    function sortedRows() {
      const column = columns.find(candidate => candidate.key === sort.key) || columns[3];
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
                : { key: column.key, direction: rows.length && typeof column.value(rows[0]) === "number" ? "desc" : "asc" };
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

    function drawRows() {
      tbody.replaceChildren(...sortedRows().slice(0, 250).map(player => {
        const row = node("tr", { class: player.player_id === selectedId ? "is-selected" : "", tabindex: "0" }, columns.map(column => node("td", {}, column.render ? column.render(player) : formatValue(column.value(player)))));
        row.onclick = () => onSelect?.(player);
        row.onkeydown = event => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect?.(player); }
        };
        return row;
      }));
    }

    drawHeader();
    drawRows();
    return node("div", { class: "table-wrap players-overview-table", tabindex: "0", role: "region", "aria-label": "Jogadores filtrados" }, [
      node("table", {}, [thead, tbody]),
    ]);
  }

  function profileStandingLabel(percentile, favorable = null, universe = "da posição") {
    const value = number(percentile);
    if (value === null) return null;
    if (value >= 99) return `Top 1% ${universe}`;
    if (value >= 95) return `Top 5% ${universe}`;
    if (value >= 90) return `Top 10% ${universe}`;
    if (value >= 75) return "Acima da média";
    if (value >= 45) return "Próximo da média";
    return favorable === false ? "Abaixo da média" : "Faixa inferior";
  }

  function metricWithComparison(labelText, value, { unit = "", benchmark = null, benchmarkLabel = "Média comparativa", compactBenchmark = false, standingUniverse = "da posição", entityValueLabel = "Valor do jogador", universeDescription = "jogadores da mesma posição na competição", entityGames = null } = {}) {
    if (!metricAvailable(value)) return null;
    const formatted = `${formatValue(value)}${unit}`;
    if (!benchmark) return node("div", { class: "profile-comparison-metric" }, [node("dt", { text: labelText }), node("dd", { text: formatted })]);
    const delta = number(benchmark.delta), percentile = number(benchmark.percentile), average = number(benchmark.average_value);
    const favorable = delta === null ? null : benchmark.direction === "lower" ? delta < 0 : delta > 0;
    const reference = compactBenchmark ? "média" : benchmarkLabel.toLocaleLowerCase("pt-BR");
    const deltaText = delta === null ? null : `${delta > 0 ? "+" : ""}${formatValue(delta)}${unit} vs ${reference}`;
    const standingText = percentile !== null ? profileStandingLabel(percentile, favorable, standingUniverse) : null;
    const smallSample = number(entityGames) !== null && number(entityGames) < 5;
    const sampleBadge = standingText && standingText !== "Próximo da média" && smallSample
      ? node("span", { class: "profile-sample-badge", title: "Recorte com poucos jogos — interprete o percentil com cautela.", text: `amostra: ${formatValue(entityGames)} ${number(entityGames) === 1 ? "jogo" : "jogos"}` })
      : null;
    const title = `${benchmarkLabel}: ${formatValue(average)}${unit} · ${entityValueLabel}: ${formatted} · Percentil: ${formatValue(percentile)} · Universo comparado: ${universeDescription} · Amostra: ${formatValue(benchmark.sample_size)}`;
    return node("div", { class: `profile-comparison-metric${favorable === true ? " is-positive" : favorable === false ? " is-negative" : ""}`, title }, [
      node("dt", { text: labelText }), node("dd", { text: formatted }),
      deltaText ? node("small", { text: deltaText }) : null,
      standingText ? node("span", { class: "profile-standing", text: standingText }) : null,
      sampleBadge,
    ]);
  }

  function profileSummaryLine(metrics) {
    return node("dl", { class: "profile-comparison-summary" }, metrics.filter(Boolean));
  }

  function profileQuickRead(name, metricOptions, benchmarks) {
    const available = metricOptions.map(([key, labelText, unit = ""]) => ({ key, labelText, unit, benchmark: benchmarks?.metrics?.[key] })).filter(item => item.benchmark && number(item.benchmark.percentile) !== null);
    if (!available.length) return null;
    const strongest = available.sort((left, right) => number(right.benchmark.percentile) - number(left.benchmark.percentile))[0];
    const value = strongest.benchmark.selected_value;
    const percentile = strongest.benchmark.percentile;
    const tone = percentile >= 90 ? "está entre a elite" : percentile >= 70 ? "se destaca" : percentile >= 45 ? "está próximo da média" : "fica abaixo da média";
    const standing = profileStandingLabel(percentile)?.toLocaleLowerCase("pt-BR");
    return node("p", { class: "profile-quick-read", text: `${name} ${tone} em ${strongest.labelText.toLocaleLowerCase("pt-BR")}: ${formatValue(value)}${strongest.unit}${standing ? `, ${standing}` : ""}, no comparativo com ${String(benchmarks?.label || "a posição").toLocaleLowerCase("pt-BR")}.` });
  }

  function distributionWithBenchmark(shots, benchmarkRows, field, title) {
    if (!shots.length) return null;
    const labels = field === "body_part" ? BODY_PART_LABELS : SHOT_TYPE_LABELS;
    const counts = [...shots.reduce((map, shot) => { const key = String(shot[field] || "Não informado"); map.set(key, (map.get(key) || 0) + 1); return map; }, new Map()).entries()].sort((a, b) => b[1] - a[1]);
    const benchmark = new Map((benchmarkRows || []).map(row => [String(row.label), number(row.percentage) || 0]));
    return node("article", { class: "player-distribution-panel benchmark-distribution" }, [
      node("h3", { text: title }),
      node("p", { class: "profile-radar-note", text: "Percentual dos chutes do jogador; marcador indica a média da posição." }),
      node("div", { class: "player-distribution-bars" }, counts.map(([rawLabel, count]) => {
      const percentage = count / shots.length * 100, reference = benchmark.get(rawLabel);
      const labelText = labels[rawLabel.toLowerCase()] || label(rawLabel);
      return node("div", { class: "player-distribution-row", title: `${labelText}: ${formatValue(percentage)}% · Média: ${formatValue(reference)}%` }, [
        node("span", { text: labelText }),
        node("span", { class: "player-distribution-track" }, [node("span", { style: `width:${percentage}%` }), reference !== undefined ? node("i", { style: `left:${Math.min(100, reference)}%`, "aria-hidden": "true" }) : null]),
        node("strong", { text: `${formatValue(percentage)}%` }),
        reference !== undefined ? node("small", { text: `média ${formatValue(reference)}%` }) : null,
      ]);
    }))]);
  }

  function teamMatchProductionChart(matches, benchmarks) {
    const rows = [...matches].filter(match => metricAvailable(match.xg_for) && metricAvailable(match.xg_against)).sort((left, right) => String(left.match_date || "9999").localeCompare(String(right.match_date || "9999")));
    if (!rows.length) return emptyState("Produção jogo a jogo indisponível", "Não há xG por partida suficiente para esta visualização.");
    const width = 760, height = 330, pad = 46, top = 34, bottom = 72, groupWidth = (width - pad * 2) / rows.length;
    const benchmark = number(benchmarks?.metrics?.xg_per_game?.average_value) || 0;
    const max = Math.max(benchmark, ...rows.flatMap(row => [number(row.xg_for) || 0, number(row.xg_against) || 0]), 1);
    const yAt = value => height - bottom - value / max * (height - top - bottom);
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "xG criado e cedido por partida" });
    if (benchmark) svg.append(svgNode("line", { x1: pad, y1: yAt(benchmark), x2: width - pad, y2: yAt(benchmark), class: "profile-benchmark-line" }));
    rows.forEach((row, index) => {
      const center = pad + groupWidth * index + groupWidth / 2, barWidth = Math.min(28, groupWidth / 3);
      [[row.xg_for, -barWidth, "is-for"], [row.xg_against, 2, "is-against"]].forEach(([value, offset, className]) => {
        const y = yAt(number(value) || 0), bar = svgNode("rect", { x: center + offset, y, width: barWidth - 2, height: height - bottom - y, class: `team-production-bar ${className}`, tabindex: "0" });
        svg.append(attachChartTooltip(bar, `${displayTeamName(row.opponent)} · ${formatMatchDate(row.match_date).split(",")[0]} · ${homeStageLabel(row)} · placar ${formatValue(row.goals_for)}–${formatValue(row.goals_against)} · ${formatValue(row.xg_for)} xG criado · ${formatValue(row.xg_against)} xG cedido · ${formatValue(row.shots_for)} finalizações · ${formatValue(row.shots_against)} sofridas`));
      });
      const opponent = displayTeamName(row.opponent);
      svg.append(
        svgNode("text", { x: center, y: height - 39, class: "chart-axis team-match-axis-opponent", "text-anchor": "middle" }, `vs ${opponent.length > 13 ? `${opponent.slice(0, 12)}…` : opponent}`),
        svgNode("text", { x: center, y: height - 20, class: "chart-axis team-match-axis-context", "text-anchor": "middle" }, `${formatMatchDate(row.match_date).split(",")[0]} · ${homeStageLabel(row)}`),
      );
    });
    return node("div", { class: "team-production-chart" }, [node("div", { class: "svg-chart" }, svg), node("div", { class: "profile-chart-legend" }, [node("span", { class: "is-for", text: "xG criado" }), node("span", { class: "is-against", text: "xG cedido" }), benchmark ? node("span", { class: "is-benchmark", text: "Média da Copa" }) : null])]);
  }

  function profileComparablesBlock(items, kind, currentId = null) {
    if (!items?.length) return null;
    return node("section", { class: "profile-comparables" }, [
      node("h3", { text: "Comparáveis" }),
      node("p", { class: "profile-comparables-note", text: "Perfis estatísticos mais próximos: menor distância entre as notas dos eixos do radar comparativo — semelhança de estilo, não de qualidade absoluta." }),
      node("div", { class: "profile-comparables-list" }, items.map(item => node("div", { class: "profile-comparable-item" }, [
        node("button", { type: "button", class: "profile-comparable-open", onclick: () => goToProfile(kind, item.id) }, [
          flagNode({ team_name: item.team_name }),
          node("span", {}, [
            node("strong", { text: kind === "player" ? item.name : displayTeamName(item.name) }),
            kind === "player" ? node("small", { text: displayTeamName(item.team_name) }) : null,
          ].filter(Boolean)),
        ]),
        currentId ? node("button", {
          type: "button", class: "action-link profile-comparable-compare",
          text: "Comparar",
          onclick: () => goToCompare(kind, currentId, item.id),
        }) : null,
      ].filter(Boolean)))),
    ]);
  }

  function insightEvidence(benchmarks, entries) {
    return entries.map(([key, labelText, unit = ""]) => {
      const benchmark = benchmarks?.metrics?.[key];
      if (!benchmark || !metricAvailable(benchmark.selected_value)) return null;
      const percentile = number(benchmark.percentile);
      const title = `${labelText}: ${formatValue(benchmark.selected_value)}${unit} · Média comparativa: ${formatValue(benchmark.average_value)}${unit}${percentile !== null ? ` · Percentil: ${formatValue(percentile)}` : ""}`;
      return node("span", { class: "insight-evidence", title }, [
        node("strong", { text: `${formatValue(benchmark.selected_value)}${unit}` }),
        node("span", { text: labelText }),
      ]);
    }).filter(Boolean);
  }

  function insightCard(insight) {
    return node("article", { class: `insight-card${insight.tone ? ` is-${insight.tone}` : ""}${insight.side ? ` is-side-${insight.side}` : ""}` }, [
      insight.tag ? node("span", { class: "insight-tag", text: insight.tag }) : null,
      node("h4", { text: insight.title }),
      node("p", { text: insight.text }),
      insight.evidence?.length ? node("div", { class: "insight-evidence-row" }, insight.evidence) : null,
    ].filter(Boolean));
  }

  function insightSection(title, subtitle, insights, className = "") {
    if (!insights?.length) return null;
    return node("section", { class: `profile-insights ${className}`.trim() }, [
      node("header", {}, [node("h3", { text: title }), subtitle ? node("p", { text: subtitle }) : null].filter(Boolean)),
      node("div", { class: "insight-grid" }, insights.map(insightCard)),
    ]);
  }

  function playerContextInsights(data) {
    const player = data.player || data.summary || {};
    const benchmarks = data.benchmarks || {};
    const dimensions = data.radar_dimensions || {};
    if (!Object.keys(benchmarks.metrics || {}).length) return [];
    const pct = key => number(benchmarks.metrics?.[key]?.percentile);
    const dim = name => number(dimensions?.[name]?.score);
    const ev = entries => insightEvidence(benchmarks, entries);
    const name = personName(player);
    const isGoalkeeper = player.macroposition === "Goleiro" || positionLabel(player.position) === "GOL";
    const found = [];
    const add = (score, insight) => found.push({ score, ...insight });

    if (isGoalkeeper) {
      const saves = pct("saves_per_90");
      if (saves !== null && saves >= 70) add(saves, {
        tag: "Times pressionados",
        title: "Rende quando é exigido",
        text: `${name} acumula defesas em alto volume. Combina com equipes que protegem a área e aceitam períodos de pressão.`,
        evidence: ev([["saves_per_90", "defesas por 90"], ["saves", "defesas"]]),
      });
      const longBall = pct("long_pass_accuracy");
      if (longBall !== null && longBall >= 70) add(longBall, {
        tag: "Jogo direto",
        title: "Lançamento como arma",
        text: `A precisão no passe longo ajuda a pular pressão. Bom encaixe para saídas rápidas e jogo direto.`,
        evidence: ev([["long_pass_accuracy", "precisão de passe longo", "%"]]),
      });
      const shortPass = pct("pass_accuracy");
      if (shortPass !== null && shortPass >= 70) add(shortPass, {
        tag: "Construção curta",
        title: "Confiável com a bola nos pés",
        text: `${name} sustenta a saída curta com segurança. Encaixa em equipes que constroem desde o goleiro.`,
        evidence: ev([["pass_accuracy", "precisão de passe", "%"], ["accurate_passes", "passes certos"]]),
      });
    } else {
      const areaThreat = pct("xg_per_90"), shotQuality = pct("xg_per_shot"), shotVolume = pct("shots_per_90");
      if (areaThreat !== null && areaThreat >= 70 && (shotQuality === null || shotQuality >= 55)) add(areaThreat, {
        tag: "Jogo direto e bolas na área",
        title: "Faro de área",
        text: `${name} gera chances perto do gol. Quanto mais a equipe chega à área, maior tende a ser o impacto.`,
        evidence: ev([["xg_per_90", "xG por 90"], ["xg_per_shot", "xG por finalização"], ["goals_per_90", "gols por 90"]]),
      });
      if (shotVolume !== null && shotVolume >= 70 && (shotQuality === null || shotQuality < 45)) add(shotVolume, {
        tag: "Domínio territorial",
        title: "Finalizador de volume",
        text: `${name} finaliza muito, inclusive de zonas difíceis. Funciona melhor com domínio territorial e sobras no campo ofensivo.`,
        evidence: ev([["shots_per_90", "finalizações por 90"], ["shots", "finalizações"]]),
      });
      const creation = Math.max(pct("xa_per_90") ?? -1, pct("key_passes_per_90") ?? -1);
      if (creation >= 70) add(creation, {
        tag: "Times de posse",
        title: "Abastece quem finaliza",
        text: `${name} cria em ritmo alto. Precisa de movimentação ao redor para transformar passe em chance.`,
        evidence: ev([["xa_per_90", "xA por 90"], ["key_passes_per_90", "passes para finalização por 90"], ["assists", "assistências"]]),
      });
      const passSafety = pct("pass_accuracy"), passVolume = pct("accurate_passes");
      if (passSafety !== null && passSafety >= 75 && (passVolume === null || passVolume >= 55)) add(passSafety, {
        tag: "Controle de jogo",
        title: "Circulação confiável",
        text: `${name} erra pouco e dá fluidez à posse. Perfil útil para equipes que constroem com paciência.`,
        evidence: ev([["pass_accuracy", "precisão de passe", "%"], ["accurate_passes", "passes certos"]]),
      });
      const progression = dim("Progressão");
      if (progression !== null && progression >= 68) add(progression, {
        tag: "Transições",
        title: "Motor de progressão",
        text: `${name} leva a bola para frente por passe e condução. Cresce em campo aberto.`,
      });
      const pressing = dim("Pressão");
      if (pressing !== null && pressing >= 68) add(pressing, {
        tag: "Pressão alta",
        title: "Primeiro defensor",
        text: `${name} pressiona acima da média da função. Ajuda equipes que querem recuperar logo após a perda.`,
      });
      const duels = pct("duels_won");
      if (duels !== null && duels >= 72) add(duels, {
        tag: "Jogo físico",
        title: "Vence o contato",
        text: `${name} vence duelos em volume alto. Ganha valor em jogos físicos e de segunda bola.`,
        evidence: ev([["duels_won", "duelos vencidos"]]),
      });
      const aerial = pct("aerial_won");
      if (aerial !== null && aerial >= 72) add(aerial, {
        tag: "Jogo aéreo",
        title: "Domínio pelo alto",
        text: `${name} é forte pelo alto. Impacta bola parada, cruzamentos e disputas longas.`,
        evidence: ev([["aerial_won", "duelos aéreos vencidos"]]),
      });
      const anticipation = pct("interceptions");
      if (anticipation !== null && anticipation >= 75) add(anticipation, {
        tag: "Linha alta",
        title: "Leitura de jogo",
        text: `${name} antecipa passes em volume alto. Ajuda a sustentar linhas mais adiantadas.`,
        evidence: ev([["interceptions", "interceptações"], ["defensive_actions_per_90", "ações defensivas por 90"]]),
      });
      const boxDefense = pct("clearances");
      if (boxDefense !== null && boxDefense >= 75) add(boxDefense, {
        tag: "Bloco baixo",
        title: "Zelador da área",
        text: `${name} corta muito dentro da área. É útil para equipes que defendem em bloco baixo.`,
        evidence: ev([["clearances", "cortes"], ["aerial_won", "duelos aéreos vencidos"]]),
      });
      const goals = number(player.goals), xg = number(player.xg);
      if (goals !== null && xg !== null && goals >= 2 && goals - xg >= 1) add(55, {
        tone: "warning",
        tag: "Atenção",
        title: "Convertendo acima do esperado",
        text: `${name} marcou ${formatValue(goals)} gols com ${formatValue(xg)} de xG. A eficiência atual está acima do padrão esperado e pode não se sustentar em uma amostra maior.`,
      });
    }

    if (!found.length) {
      return [{
        tag: "Perfil equilibrado",
        title: "Sem picos claros neste recorte",
        text: `${name} não tem um pico estatístico claro neste recorte. Perfil funcional, sem especialidade dominante nos dados.`,
      }];
    }
    return found.sort((left, right) => right.score - left.score).slice(0, 4);
  }

  function playerContextSection(data) {
    const insights = playerContextInsights(data);
    if (!insights.length) return null;
    const games = number(data.player?.games ?? data.summary?.games);
    const caution = games !== null && games < 3 ? ` Amostra de ${formatValue(games)} ${games === 1 ? "jogo" : "jogos"} — leia como tendência, não veredito.` : "";
    return insightSection(
      "Contextos de destaque",
      `Onde este perfil tende a render melhor, comparado à posição na Copa.${caution}`,
      insights,
    );
  }

  function teamDiagnosisInsights(data) {
    const team = data.team || {};
    const benchmarks = data.benchmarks || {};
    if (!Object.keys(benchmarks.metrics || {}).length) return [];
    const pct = key => number(benchmarks.metrics?.[key]?.percentile);
    const ev = entries => insightEvidence(benchmarks, entries);
    const name = teamName(team);
    const found = [];
    const add = (score, insight) => found.push({ score, ...insight });

    const possession = pct("average_possession"), passing = pct("pass_accuracy");
    if (possession !== null && possession >= 65 && (passing === null || passing >= 55)) add(possession, {
      tag: "Domínio com a bola",
      title: "Controla o jogo pela posse",
      text: `${name} fica com a bola e circula com precisão acima da maioria da Copa. Tende a impor o ritmo, empurrar o adversário para trás e atacar contra blocos fechados — e fica vulnerável a contra-ataques quando a recomposição falha.`,
      evidence: ev([["average_possession", "posse média", "%"], ["pass_accuracy", "precisão de passe", "%"]]),
    });
    const attack = pct("xg_per_game"), volume = pct("shots_per_game"), conversion = pct("conversion");
    if (possession !== null && possession <= 40 && attack !== null && attack >= 55) add(attack, {
      tag: "Transição",
      title: "Perigosa sem precisar da bola",
      text: `${name} cria acima da maioria mesmo com menos posse — perfil de jogo direto e transições. Costuma ceder o campo e atacar os espaços que aparecem.`,
      evidence: ev([["xg_per_game", "xG por jogo"], ["average_possession", "posse média", "%"]]),
    });
    if (attack !== null && attack >= 65 && volume !== null && volume >= 65) {
      if (conversion !== null && conversion <= 40) add(attack, {
        tone: "warning",
        tag: "Ataque",
        title: "Cria mais do que converte",
        text: `${name} gera volume e qualidade de finalização, mas a conversão fica abaixo da maioria. Os jogos tendem a ficar abertos por mais tempo do que o domínio sugere.`,
        evidence: ev([["xg_per_game", "xG por jogo"], ["shots_per_game", "finalizações por jogo"], ["conversion", "conversão", "%"]]),
      });
      else add(attack, {
        tag: "Ataque",
        title: "Produção ofensiva de elite",
        text: `${name} combina volume de finalização e qualidade de chance criada. Poucas defesas na Copa seguram essa produção por 90 minutos.`,
        evidence: ev([["xg_per_game", "xG por jogo"], ["shots_per_game", "finalizações por jogo"], ["goals_per_game", "gols por jogo"]]),
      });
    }
    if (conversion !== null && conversion >= 70 && volume !== null && volume <= 45) add(conversion, {
      tag: "Ataque",
      title: "Ataque cirúrgico",
      text: `${name} finaliza pouco, mas converte muito. É um estilo eficiente e de margem curta: quando a pontaria cai, a produção baixa não compensa.`,
      evidence: ev([["conversion", "conversão", "%"], ["shots_per_game", "finalizações por jogo"]]),
    });
    const efficiency = pct("goals_minus_xg");
    if (efficiency !== null && efficiency >= 70) add(efficiency, {
      tone: "warning",
      tag: "Eficiência",
      title: "Vencendo acima do xG",
      text: `${name} marca mais do que a produção esperada indica. A eficiência vem decidindo jogos — e tende a regredir se o padrão de criação não subir junto.`,
      evidence: ev([["goals_minus_xg", "gols acima do xG"], ["conversion", "conversão", "%"]]),
    });
    if (efficiency !== null && efficiency <= 30) add(80 - efficiency, {
      tag: "Eficiência",
      title: "Produz mais do que marca",
      text: `${name} cria mais do que converte em gols. Se o padrão de criação se mantiver, os resultados tendem a melhorar sem mudança de estilo.`,
      evidence: ev([["goals_minus_xg", "gols acima do xG"], ["xg_per_game", "xG por jogo"]]),
    });
    const defenseQuality = pct("xga_per_game"), defenseVolume = pct("shots_against_per_game");
    if (defenseQuality !== null && defenseQuality >= 65 && (defenseVolume === null || defenseVolume >= 55)) add(defenseQuality, {
      tag: "Defesa",
      title: "Defesa sob controle",
      text: `${name} cede pouco em volume e em qualidade de chance. Adversários precisam de bola parada ou erro individual para criar perigo real.`,
      evidence: ev([["xga_per_game", "xG cedido por jogo"], ["shots_against_per_game", "finalizações sofridas por jogo"]]),
    });
    if (defenseQuality !== null && defenseQuality <= 35) add(80 - defenseQuality, {
      tone: "warning",
      tag: "Defesa",
      title: "Defesa exposta",
      text: `${name} cede chances claras com frequência acima da maioria da Copa. Ataques diretos e transições rápidas tendem a encontrar espaço.`,
      evidence: ev([["xga_per_game", "xG cedido por jogo"], ["goals_against_per_game", "gols sofridos por jogo"]]),
    });
    const recoveries = pct("recoveries_per_game"), tackles = pct("tackles_per_game");
    if (recoveries !== null && recoveries >= 65 && (tackles === null || tackles >= 50)) add(recoveries, {
      tag: "Pressão",
      title: "Recupera a bola rápido",
      text: `${name} recupera a posse em volume alto — perfil de pressão após a perda. Costuma transformar o campo adversário em zona de construção.`,
      evidence: ev([["recoveries_per_game", "recuperações por jogo"], ["tackles_per_game", "desarmes por jogo"]]),
    });
    const balance = pct("xg_difference");
    if (balance !== null && balance >= 80) add(balance, {
      tag: "Campanha",
      title: "Dominante nos dois lados",
      text: `${name} tem um dos melhores saldos de xG da Copa: cria muito e cede pouco. É o tipo de campanha que costuma ir longe no mata-mata.`,
      evidence: ev([["xg_difference", "saldo de xG"]]),
    });

    if (!found.length) {
      return [{
        tag: "Perfil equilibrado",
        title: "Campanha sem extremos",
        text: `${name} não apresenta forças ou fragilidades marcantes em relação à média da Copa neste recorte — os jogos tendem a ser decididos em detalhes e bola parada.`,
      }];
    }
    return found.sort((left, right) => right.score - left.score).slice(0, 5);
  }

  function teamDiagnosisSection(data) {
    const insights = teamDiagnosisInsights(data);
    if (!insights.length) return null;
    return insightSection(
      "Diagnóstico da seleção",
      "Como esta seleção costuma jogar, lido a partir das métricas da campanha em relação às demais seleções da Copa.",
      insights,
    );
  }

  function playerRadarFeature(player, radar, benchmarkRadar, benchmarkLabel, leaderRadar = []) {
    if (radar.length < 4 || benchmarkRadar.length < 4) return null;
    const title = `${personName(player)} vs ${benchmarkLabel.toLocaleLowerCase("pt-BR")}`;
    const leaderLabel = "Líder da posição";
    return node("section", { class: "profile-radar-feature" }, [
      node("header", {}, [node("h3", { text: "Radar comparativo" }), node("p", { text: title })]),
      radarChart(radar, title, benchmarkRadar, benchmarkLabel, true, leaderRadar, leaderLabel),
      node("p", { class: "profile-radar-note", text: `Escala 0–100. A linha cinza representa ${benchmarkLabel.toLocaleLowerCase("pt-BR")} da Copa${leaderRadar.length ? `; a linha pontilhada mostra o melhor valor observado na posição em cada eixo` : ""}.` }),
    ]);
  }

  function playerShotExperience(data, metric) {
    const shots = data.shot_map || [];
    return node("div", { class: "profile-shot-experience" }, [
      profileSummaryLine([
        metric("shots", "Finalizações"), metric("goals", "Gols"),
        metric("xg", "xG"), metric("shot_conversion", "Conversão", "%"),
        metric("xg_per_shot", "xG por finalização"),
      ]),
      node("section", { class: "profile-shot-map-section" }, [node("h3", { text: "Mapa de finalizações" }), playerShotMapPanel(shots)]),
      node("div", { class: "player-distribution-grid" }, [playerShotMinuteChart(shots, data.shot_benchmark?.minute_bins), playerShotQualityChart(shots)]),
      node("div", { class: "player-distribution-grid" }, [
        distributionWithBenchmark(shots, data.shot_benchmark?.distributions?.body_part, "body_part", "Parte do corpo"),
        distributionWithBenchmark(shots, data.shot_benchmark?.distributions?.shot_type, "shot_type", "Situação da finalização"),
      ]),
    ]);
  }

  function playerProfileView(data, activeTab = "general") {
    if (!data?.available) return emptyState("Sem dados neste recorte", data?.notice || "Escolha outro recorte para continuar.");
    const player = data.player || data.summary || {};
    const benchmarks = data.benchmarks || {}, benchmarkLabel = benchmarks.label || "Média da posição";
    const isGoalkeeper = player.macroposition === "Goleiro" || positionLabel(player.position) === "GOL";
    const isDefender = player.macroposition === "Defensor" || positionLabel(player.position) === "DEF";
    const isMidfielder = player.macroposition === "Meio-campista" || positionLabel(player.position) === "MEI";
    const availableRadar = (data.radar || player.radar || []).filter(axis => metricAvailable(axis.value));
    const benchmarkRadar = (data.benchmark_radar || []).filter(axis => availableRadar.some(selected => selected.axis === axis.axis));
    const leaderRadar = (data.leader_radar || []).filter(axis => availableRadar.some(selected => selected.axis === axis.axis));
    const metric = (key, labelText, unit = "", compactBenchmark = false) => metricWithComparison(labelText, player[key], { unit, benchmark: benchmarks.metrics?.[key], benchmarkLabel, compactBenchmark, entityGames: number(player.games) });
    const metricGroupRows = (title, rows) => rows.length ? node("section", { class: "profile-metric-group" }, [node("header", {}, [node("h4", { text: title }), node("small", { text: `Comparativo: ${benchmarkLabel}` })]), node("dl", { class: "profile-comparison-grid" }, rows)]) : null;
    const metricGroup = (title, definitions) => metricGroupRows(title, definitions.map(([key, labelText, unit]) => metric(key, labelText, unit, true)).filter(Boolean));
    const duelsGroup = () => {
      const rows = [metric("duels_won", "Duelos vencidos", "", true), metric("aerial_won", "Duelos aéreos vencidos", "", true)].filter(Boolean);
      const won = number(player.duels_won), lost = number(player.duels_lost);
      if (won !== null && lost !== null && won + lost > 0) {
        rows.push(metricWithComparison("Aproveitamento em duelos", Math.round((won / (won + lost)) * 1000) / 10, { unit: "%", compactBenchmark: true }));
      }
      return metricGroupRows("Duelos", rows);
    };
    const summaryDefinitions = isGoalkeeper
      ? [["minutes_played", "Minutos", " min"], ["games", "Jogos", ""], ["saves", "Defesas", ""], ["saves_per_90", "Defesas por 90", ""], ["rating", "Rating", ""]]
      : [["minutes_played", "Minutos", " min"], ["games", "Jogos", ""], ["goals", "Gols", ""], ["xg", "xG", ""], ["shots", "Finalizações", ""], ["shot_conversion", "Conversão", "%"]];
    const quickMetrics = isGoalkeeper
      ? [["saves_per_90", "defesas por 90"], ["pass_accuracy", "precisão de passe", "%"], ["rating", "rating médio"]]
      : isDefender
        ? [["defensive_actions_per_90", "ações defensivas por 90"], ["duels_won", "duelos vencidos"], ["pass_accuracy", "precisão de passe", "%"]]
        : isMidfielder
          ? [["xa_per_90", "xA por 90"], ["key_passes_per_90", "passes para finalização por 90"], ["pass_accuracy", "precisão de passe", "%"]]
          : [["goals_per_90", "gols por 90"], ["xg_per_90", "xG por 90"], ["shot_conversion", "conversão", "%"]];
    let content;
    if (activeTab === "shots" && !isGoalkeeper) {
      content = playerShotExperience(data, metric);
    } else if (activeTab === "match_log") {
      content = playerMatchLogTable(data.match_log || []);
    } else {
      const radarFeature = playerRadarFeature(player, availableRadar, benchmarkRadar, benchmarkLabel, leaderRadar);
      content = node("div", { class: "player-profile-general" }, [
        profileQuickRead(personName(player), quickMetrics, benchmarks),
        playerContextSection(data),
        radarFeature,
        node("div", { class: "profile-metric-groups" }, (isGoalkeeper ? [
          metricGroup("Defesa do gol", [["saves", "Defesas", ""], ["saves_per_90", "Defesas por 90", ""], ["rating", "Rating médio", ""]]),
          metricGroup("Distribuição", [["accurate_passes", "Passes certos", ""], ["pass_accuracy", "Precisão de passe", "%"], ["long_pass_accuracy", "Bolas longas certas", "%"]]),
        ] : [
          // Same 6 blocks for every outfield position (Ataque, Criação, Participação, Duelos,
          // Passe, Defesa), matching the 6 axes of the radar 1:1 — a block that has no data for
          // this player's sample simply hides itself (metricGroup returns null when empty),
          // rather than showing a position a fixed subset that leaves some radar axes orphaned.
          metricGroup("Finalização", [["goals_per_90", "Gols por 90", ""], ["xg_per_90", "xG por 90", ""], ["shots_per_90", "Finalizações por 90", ""], ["xg_per_shot", "xG por finalização", ""]]),
          metricGroup("Criação", [["assists", "Assistências", ""], ["xa_per_90", "xA por 90", ""], ["key_passes_per_90", "Passes para finalização por 90", ""]]),
          metricGroup("Participação", [["goal_involvements", "Participações em gols", ""], ["goal_involvements_per_90", "Participações por 90", ""], ["rating", "Rating médio", ""]]),
          duelsGroup(),
          metricGroup("Passe", [["accurate_passes", "Passes certos", ""], ["pass_accuracy", "Precisão de passe", "%"], ["long_pass_accuracy", "Bolas longas certas", "%"]]),
          metricGroup("Defesa", [["tackles", "Desarmes", ""], ["interceptions", "Interceptações", ""], ["clearances", "Cortes", ""]]),
        ]).filter(Boolean)),
        profileComparablesBlock(data.comparable_players, "player", player.player_id),
      ].filter(Boolean));
    }
    return node("article", { class: "player-profile-view" }, [
      node("header", { class: "player-profile-identity" }, [playerPhotoNode(player), node("span", {}, [node("small", { class: "player-profile-team", text: `${displayTeamName(player.team_name)} · ${resolvedPlayerPosition(player)}` }), node("h3", { text: personName(player) })]), node("button", { type: "button", class: "profile-compare-shortcut", text: "Comparar com outro jogador", onclick: () => goToCompare("player", player.player_id) })]),
      profileSummaryLine(summaryDefinitions.map(([key, labelText, unit]) => metric(key, labelText, unit))),
      node("div", { class: "player-profile-content" }, content),
    ]);
  }

  function playerMatchLogTable(logs) {
    if (!logs.length) return emptyState("Jogos indisponíveis", "Não há atuações registradas neste recorte.");
    const ordered = [...logs].sort((left, right) => String(left.match_date || "9999").localeCompare(String(right.match_date || "9999")));
    const shortDate = value => {
      const date = new Date(value || "");
      return Number.isNaN(date.getTime()) ? "Data não informada" : new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "short" }).format(date).replace(".", "");
    };
    const participated = log => log.participated !== false && number(log.minutes_played) > 0;
    const context = log => `${shortDate(log.match_date)} · ${homeStageLabel(log)}`;
    const table = node("div", { class: "table-wrap player-match-log" }, [node("table", {}, [
      node("thead", {}, node("tr", {}, ["Partida", "Data / fase", "Min.", "Gols", "xG", "Finalizações", "No alvo", "Rating"].map(labelText => node("th", { text: labelText })))),
      node("tbody", {}, ordered.map(log => participated(log)
        ? node("tr", {}, [
          node("td", { text: translateTeamsInText(log.match) }), node("td", { text: context(log) }), node("td", { text: formatValue(log.minutes_played) }),
          node("td", { text: formatValue(log.goals) }), node("td", { text: formatValue(log.xg) }), node("td", { text: formatValue(log.shots) }),
          node("td", { text: formatValue(log.shots_on_target) }), node("td", { text: metricAvailable(log.rating) && number(log.rating) > 0 ? formatValue(log.rating) : "—" }),
        ])
        : node("tr", { class: "is-dnp" }, [node("td", { text: translateTeamsInText(log.match) }), node("td", { text: context(log) }), node("td", { colspan: "6", text: "Não participou" })]))),
    ])]);
    return node("div", { class: "player-match-log-view" }, [table, playerMatchLogCards(ordered)]);
  }

  function playerMatchLogCards(logs) {
    return node("div", { class: "player-match-cards" }, logs.map(log => {
      const didPlay = log.participated !== false && number(log.minutes_played) > 0;
      const date = new Date(log.match_date || "");
      const dateLabel = Number.isNaN(date.getTime()) ? "Data não informada" : new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "short" }).format(date).replace(".", "");
      return node("article", { class: `player-match-card${didPlay ? "" : " is-dnp"}` }, [
        node("header", {}, [node("strong", { text: translateTeamsInText(log.match) }), node("span", { text: `${dateLabel} · ${homeStageLabel(log)}` })]),
        didPlay ? node("dl", {}, [["Min.", log.minutes_played], ["Gols", log.goals], ["xG", log.xg], ["Finalizações", log.shots], ["No alvo", log.shots_on_target], ["Rating", number(log.rating) > 0 ? log.rating : "—"]].map(([labelText, value]) => node("div", {}, [node("dt", { text: labelText }), node("dd", { text: formatValue(value) })]))) : node("p", { text: "Não participou" }),
      ]);
    }));
  }

  function playerShotMapPanel(shots, { color = null } = {}) {
    if (!shots.length) return emptyState("Mapa de finalizações indisponível", "Não há chutes registrados neste recorte.");
    const state = { mode: "all", body: "all", type: "all", match: "all" };
    const output = node("div");
    const modes = [["all", "Todos"], ["goals", "Gols"], ["on_target", "No alvo"], ["high_xg", "xG alto"]];
    const buttons = modes.map(([key, labelText]) => node("button", { type: "button", text: labelText, onclick: () => { state.mode = key; draw(); } }));
    const bodySelect = node("select", {}, [node("option", { value: "all", text: "Todas" }), ...[...new Set(shots.map(shot => shot.body_part).filter(Boolean))].map(value => node("option", { value, text: BODY_PART_LABELS[String(value).toLowerCase()] || label(value) }))]);
    const typeSelect = node("select", {}, [node("option", { value: "all", text: "Todas" }), ...[...new Set(shots.map(shot => shot.shot_type).filter(Boolean))].map(value => node("option", { value, text: SHOT_TYPE_LABELS[String(value).toLowerCase()] || label(value) }))]);
    const matchOptions = [...new Map(shots.filter(shot => shot.match_id).map(shot => [String(shot.match_id), `${displayTeamName(shot.home_team)} ${formatValue(shot.home_score)}–${formatValue(shot.away_score)} ${displayTeamName(shot.away_team)}`])).entries()];
    const matchSelect = node("select", {}, [node("option", { value: "all", text: "Todas as partidas" }), ...matchOptions.map(([value, labelText]) => node("option", { value, text: labelText }))]);
    const controls = node("div", { class: "player-shot-controls" }, [
      node("div", { class: "segmented-control" }, buttons),
      node("label", {}, [node("span", { text: "Parte do corpo" }), bodySelect]),
      node("label", {}, [node("span", { text: "Situação" }), typeSelect]),
      node("label", {}, [node("span", { text: "Partida" }), matchSelect]),
    ]);
    function draw() {
      buttons.forEach((button, index) => {
        const active = modes[index][0] === state.mode;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });
      const filtered = shots.filter(shot => {
        const xg = number(shot.xg ?? shot.statsbomb_xg) || 0;
        return (state.mode === "all" || (state.mode === "goals" && shot.is_goal) || (state.mode === "on_target" && shot.is_on_target) || (state.mode === "high_xg" && xg >= .2))
          && (state.body === "all" || shot.body_part === state.body)
          && (state.type === "all" || shot.shot_type === state.type)
          && (state.match === "all" || String(shot.match_id) === state.match);
      });
      const map = playerShotMap(filtered, { color });
      output.replaceChildren(map ? node("div", {}, [map, shotSummary(filtered)].filter(Boolean)) : emptyState("Mapa de finalizações indisponível", "Não há chutes neste recorte."));
    }
    bodySelect.onchange = event => { state.body = event.target.value; draw(); };
    typeSelect.onchange = event => { state.type = event.target.value; draw(); };
    matchSelect.onchange = event => { state.match = event.target.value; draw(); };
    draw();
    return node("div", { class: "player-shot-analysis" }, [controls, output]);
  }

  function playerShotMinuteChart(shots, benchmarkBins = []) {
    if (!shots.length) return emptyState("Distribuição temporal indisponível", "Não há finalizações neste recorte.");
    const ranges = [[0, 15, "0–15"], [16, 30, "16–30"], [31, 45, "31–45+"], [46, 60, "46–60"], [61, 75, "61–75"], [76, 90, "76–90"], [91, Infinity, "90+"]];
    const benchmark = new Map((benchmarkBins || []).map(row => [row.label, number(row.average_shots) || 0]));
    const bins = ranges.map(([start, end, labelText]) => {
      const rows = shots.filter(shot => (number(shot.minute) || 0) >= start && (number(shot.minute) || 0) <= end);
      return { label: labelText, shots: rows.length, goals: rows.filter(shot => shot.is_goal).length, xg: rows.reduce((total, shot) => total + (number(shot.xg ?? shot.statsbomb_xg) || 0), 0), average: benchmark.get(labelText) };
    });
    const width = 720, height = 250, pad = 40, max = Math.max(...bins.map(bin => bin.shots), 1), barWidth = (width - pad * 2) / bins.length;
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Finalizações por faixa de minuto" });
    bins.forEach((bin, index) => {
      const h = bin.shots / max * (height - pad * 2);
      const x = pad + index * barWidth + 8, y = height - pad - h;
      const bar = svgNode("rect", { x, y, width: barWidth - 16, height: h, rx: 2, class: "player-minute-bar", tabindex: "0" });
      svg.append(attachChartTooltip(bar, `${bin.label} min · ${bin.shots} finalizações · ${bin.goals} gols · ${formatValue(bin.xg)} xG${bin.average !== undefined ? ` · Média da posição: ${formatValue(bin.average)} finalizações` : ""}`));
      if (bin.average !== undefined) {
        const benchmarkY = height - pad - Math.min(max, bin.average) / max * (height - pad * 2);
        svg.append(svgNode("line", { x1: x - 2, y1: benchmarkY, x2: x + barWidth - 14, y2: benchmarkY, class: "player-minute-benchmark" }));
      }
      if (bin.shots) svg.append(svgNode("text", { x: x + (barWidth - 16) / 2, y: Math.max(18, y - 8), class: "player-minute-value", "text-anchor": "middle" }, String(bin.shots)));
      if (bin.goals) svg.append(svgNode("circle", { cx: x + (barWidth - 16) / 2, cy: Math.max(pad, y - 7), r: 4 + bin.goals, class: "player-minute-goal" }));
      svg.append(svgNode("text", { x: x + (barWidth - 16) / 2, y: height - 16, class: "chart-axis", "text-anchor": "middle" }, bin.label));
    });
    return node("article", { class: "player-distribution-panel" }, [node("h3", { text: "Finalizações por minuto" }), node("div", { class: "svg-chart" }, svg)]);
  }

  function playerShotQualityChart(shots) {
    if (!shots.length) return emptyState("Distribuição de qualidade indisponível", "Não há finalizações neste recorte.");
    const ranges = [[0, .1, "Baixo · <0,1 xG"], [.1, .3, "Médio · 0,1–0,3 xG"], [.3, Infinity, "Alto · >0,3 xG"]];
    const bins = ranges.map(([start, end, labelText]) => {
      const rows = shots.filter(shot => { const xg = Math.max(0, number(shot.xg ?? shot.statsbomb_xg) || 0); return xg >= start && xg < end; });
      return { label: labelText, shots: rows.length, goals: rows.filter(shot => shot.is_goal).length, xg: rows.reduce((total, shot) => total + Math.max(0, number(shot.xg ?? shot.statsbomb_xg) || 0), 0) };
    });
    const width = 720, height = 250, pad = 40, max = Math.max(...bins.map(bin => bin.shots), 1), barWidth = (width - pad * 2) / bins.length;
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Finalizações por faixa de qualidade de chance" });
    bins.forEach((bin, index) => {
      const h = bin.shots / max * (height - pad * 2);
      const x = pad + index * barWidth + 8, y = height - pad - h;
      const bar = svgNode("rect", { x, y, width: barWidth - 16, height: h, rx: 2, class: "player-minute-bar", tabindex: "0" });
      svg.append(attachChartTooltip(bar, `${bin.label} · ${bin.shots} finalizações · ${bin.goals} gols · ${formatValue(bin.xg)} xG total`));
      if (bin.shots) svg.append(svgNode("text", { x: x + (barWidth - 16) / 2, y: Math.max(18, y - 8), class: "player-minute-value", "text-anchor": "middle" }, String(bin.shots)));
      if (bin.goals) svg.append(svgNode("circle", { cx: x + (barWidth - 16) / 2, cy: Math.max(pad, y - 7), r: 4 + bin.goals, class: "player-minute-goal" }));
      svg.append(svgNode("text", { x: x + (barWidth - 16) / 2, y: height - 16, class: "chart-axis", "text-anchor": "middle" }, bin.label));
    });
    return node("article", { class: "player-distribution-panel" }, [
      node("h3", { text: "Finalizações por qualidade de chance" }),
      node("p", { class: "profile-radar-note", text: "Baixa: <0,10 xG · Média: 0,10–0,29 xG · Alta: ≥0,30 xG." }),
      node("div", { class: "svg-chart" }, svg),
    ]);
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

  function matchStageLabel(matchOrStage) {
    if (isObject(matchOrStage) && matchOrStage.stage_label) return matchOrStage.stage_label;
    const raw = isObject(matchOrStage) ? matchOrStage.stage : matchOrStage;
    const normalized = String(raw || "").toLowerCase().replace(/[ -]+/g, "_");
    const labels = {
      group_stage: "Fase de grupos", round_of_32: "Fase de 32", round_of_16: "Oitavas",
      quarter_final: "Quartas", quarter_finals: "Quartas", semi_final: "Semifinais",
      semi_finals: "Semifinais", third_place: "Disputa de 3º lugar", final: "Final",
    };
    return labels[normalized] || "Fase não informada";
  }

  function matchPublicStatus(match) {
    if (match?.public_status) return match.public_status;
    const status = competitionMatchStatus(match);
    if (["Encerrado", "Ao vivo", "Aguardando resultado"].includes(status)) return status;
    if (!match?.home_defined || !match?.away_defined) return "A definir";
    const today = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
    if (match?.local_date === today) return "Hoje";
    return "Agendado";
  }

  function matchTeamLink(teamNameValue, teamId, defined) {
    const display = translateTeamsInText(teamNameValue || "A definir");
    if (!defined || !teamId) return node("span", { class: "matches-calendar-team is-placeholder", title: display }, [node("span", { text: display })]);
    return node("button", {
      type: "button", class: "matches-calendar-team", title: display,
      onclick: event => { event.stopPropagation(); goToProfile("team", teamId); },
    }, [flagNode(teamNameValue), node("span", { text: display })]);
  }


  function matchDayBadge(match) {
    const date = new Date(match?.match_date || "");
    if (Number.isNaN(date.getTime())) return null;
    const key = value => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit", day: "2-digit" }).format(value);
    const now = new Date();
    if (key(date) === key(now)) return node("b", { class: "match-day-badge is-today", text: "Hoje" });
    if (key(date) === key(new Date(now.getTime() + 864e5))) return node("b", { class: "match-day-badge", text: "Amanhã" });
    return null;
  }

  function matchCalendarRow(match, grouping) {
    const status = matchPublicStatus(match);
    const finished = status === "Encerrado";
    const live = status === "Ao vivo";
    const hasScore = match?.home_score !== null && match?.home_score !== undefined
      && match?.away_score !== null && match?.away_score !== undefined;
    const score = hasScore && (finished || live) ? `${formatValue(match.home_score)}–${formatValue(match.away_score)}` : "×";
    const row = node("article", {
      class: `matches-calendar-row is-${status.toLowerCase().replace(/[^a-záàâãéêíóôõúç]+/gi, "-")}${!match?.home_defined && !match?.away_defined ? " is-undefined" : ""}`,
      role: match?.match_id ? "link" : null, tabIndex: match?.match_id ? 0 : -1,
      "aria-label": `${translateTeamsInText(match?.home_team)} ${score} ${translateTeamsInText(match?.away_team)}. ${status}.`,
    }, [
      node("div", { class: "matches-calendar-time" }, [
        matchDayBadge(match),
        node("time", { dateTime: match?.match_date || "", title: "Horários em Brasília", text: grouping === "date" ? competitionKickoffLabel(match?.match_date).split(" · ").at(-1) : competitionKickoffLabel(match?.match_date) }),
        match?.group_name ? groupTag(match.group_name) : node("small", { text: matchStageLabel(match) }),
      ]),
      node("div", { class: "matches-calendar-scoreline" }, [
        matchTeamLink(match?.home_team, match?.home_team_id, match?.home_defined),
        hasScore && (finished || live)
          ? scoreText(match?.home_score, match?.away_score, { homeName: match?.home_team, awayName: match?.away_team })
          : node("strong", { text: score }),
        matchTeamLink(match?.away_team, match?.away_team_id, match?.away_defined),
      ]),
      node("span", { class: "matches-calendar-status", text: status }),
      node("span", { class: "matches-calendar-open", "aria-hidden": "true", text: "→" }),
    ]);
    if (match?.match_id) {
      row.addEventListener("click", () => routeTo("matches", match.match_id));
      row.addEventListener("keydown", event => {
        if (event.key === "Enter") { event.preventDefault(); routeTo("matches", match.match_id); }
      });
    }
    return row;
  }

  function matchCalendarDayLabel(value) {
    const date = new Date(`${value}T12:00:00`);
    const today = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
    const tomorrow = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date(Date.now() + 24 * 60 * 60 * 1000));
    if (value === today) return "Hoje";
    if (value === tomorrow) return "Amanhã";
    return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" }).format(date).replace(" de ", " ").replace(".", "");
  }

  function matchCalendarGroups(rows, grouping) {
    const grouped = new Map();
    rows.forEach(match => {
      const key = grouping === "stage" ? match.stage : match.local_date || "not-informed";
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(match);
    });
    return node("div", { class: `matches-calendar-list is-${grouping}` }, [...grouped].map(([key, matches]) => node("section", { class: "matches-calendar-group" }, [
      node("header", {}, [
        node("h3", { text: grouping === "stage" ? matchStageLabel(matches[0]) : key === "not-informed" ? "Data a definir" : matchCalendarDayLabel(key) }),
        node("span", { text: `${matches.length} ${matches.length === 1 ? "partida" : "partidas"}` }),
      ]),
      node("div", { class: "matches-calendar-group-list" }, matches.map(match => matchCalendarRow(match, grouping))),
    ])));
  }

  function matchFilterBar({ rows, filters, stages, selected, onChange }) {
    const selects = {};
    const pillGroups = {};
    const statusOptions = ["Encerrado", "Próximos", "Hoje", "Ao vivo", "A definir", "Aguardando resultado"]
      .filter(value => value === "Próximos" || rows.some(match => matchPublicStatus(match) === value));

    const refreshPills = () => {
      Object.entries(pillGroups).forEach(([key, group]) => {
        group.querySelectorAll("button").forEach(button => button.classList.toggle("is-active", button.dataset.value === String(selected[key])));
      });
    };
    const pillGroup = (key, options) => {
      const group = node("div", { class: "matches-filter-pills", role: "group" }, [
        node("button", { type: "button", "data-value": "all", class: "is-active", text: "Todos", onclick: () => { selected[key] = "all"; refreshPills(); onChange(); } }),
        ...options.map(([value, display]) => node("button", {
          type: "button", "data-value": value, text: display,
          onclick: () => { selected[key] = value; refreshPills(); onChange(); },
        })),
      ]);
      pillGroups[key] = group;
      return group;
    };

    const secondaryDefinitions = [
      ["Grupo", "group", (filters.groups || []).map(value => [value, `Grupo ${value}`])],
      ["Seleção", "team", (filters.teams || []).map(value => [value, displayTeamName(value)])],
      ["Data", "date", (filters.dates || []).map(value => [value, matchCalendarDayLabel(value)])],
    ];
    const secondaryFields = secondaryDefinitions.map(([labelText, key, values]) => {
      const select = node("select", { onchange: event => { selected[key] = event.target.value; onChange(); } }, [
        node("option", { value: "all", text: "Todos" }),
        ...values.map(([value, display]) => node("option", { value, text: display })),
      ]);
      selects[key] = select;
      return node("label", {}, [node("span", { text: labelText }), select]);
    });
    const hasSecondaryValues = secondaryDefinitions.some(([, , values]) => values.length);

    const setShortcut = (key, value) => {
      Object.keys(selected).filter(item => item !== "grouping").forEach(item => { selected[item] = "all"; if (selects[item]) selects[item].value = "all"; });
      selected[key] = value;
      if (selects[key]) selects[key].value = value;
      refreshPills();
      onChange();
    };
    const clear = () => setShortcut("status", "all");
    const element = node("div", { class: "matches-filter-bar" }, [
      node("div", { class: "matches-filter-primary" }, [
        node("div", { class: "matches-filter-pill-row" }, [node("small", { text: "Fase" }), pillGroup("stage", stages.map(item => [item.stage, item.stage_label]))]),
        node("div", { class: "matches-filter-pill-row" }, [node("small", { text: "Status" }), pillGroup("status", statusOptions.map(value => [value, value]))]),
      ]),
      hasSecondaryValues ? node("details", { class: "matches-filter-more" }, [
        node("summary", { text: "Mais filtros" }),
        node("div", { class: "matches-filter-grid" }, secondaryFields),
      ]) : null,
      node("div", { class: "matches-filter-actions" }, [
        node("button", { type: "button", text: "Hoje", onclick: () => setShortcut("date", new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date())) }),
        node("button", { type: "button", text: "Próximos jogos", onclick: () => setShortcut("status", "Próximos") }),
        node("button", { type: "button", text: "Encerrados", onclick: () => setShortcut("status", "Encerrado") }),
        node("button", { type: "button", class: "is-clear", text: "Limpar filtros", onclick: clear }),
      ]),
    ]);
    element.matchSelects = selects;
    return element;
  }

  function renderMatches(data) {
    const fragment = dashboardShell("Partidas", "Calendário, resultados e detalhes dos jogos da Copa 2026.", data);
    const summary = data.summary || {};
    fragment.append(node("div", { class: "matches-summary-strip" }, [
      ["Partidas", summary.matches], ["Encerradas", summary.finished], ["Próximas", summary.upcoming],
      ["Gols", summary.goals], ["Gols por jogo", summary.goals_per_match], ["Fase atual", summary.current_phase],
    ].filter(([, value]) => value !== null && value !== undefined).map(([labelText, value]) => node("div", {}, [node("strong", { text: formatValue(value) }), node("span", { text: labelText })]))));
    if (!data.items?.length) {
      fragment.append(emptyState("Calendário ainda não disponível", "As partidas aparecerão assim que forem publicadas."));
      els.view.replaceChildren(fragment);
      return;
    }
    // Hierarquia editorial: hoje/próximos e últimos resultados antes do arquivo completo.
    const isFinished = match => matchPublicStatus(match) === "Encerrado";
    const upcomingRows = data.items
      .filter(match => !isFinished(match) && matchPublicStatus(match) !== "Aguardando resultado")
      .sort((a, b) => String(a.match_date || "9999").localeCompare(String(b.match_date || "9999")))
      .slice(0, 4);
    if (upcomingRows.length) fragment.append(section("Hoje e próximos", "Horários em Brasília", node("div", { class: "matches-featured-list" }, upcomingRows.map((match, index) => compactMatchRow(match, { featured: index === 0 }))), "matches-upcoming-section"));
    const recentRows = data.items
      .filter(isFinished)
      .sort((a, b) => String(b.match_date || "").localeCompare(String(a.match_date || "")))
      .slice(0, 4);
    if (recentRows.length) fragment.append(section("Últimos resultados", null, node("div", { class: "matches-featured-list" }, recentRows.map(match => compactMatchRow(match))), "matches-recent-section"));
    const selected = { group: "all", stage: "all", team: "all", date: "all", status: "all", grouping: "date", search: "" };
    const calendarHost = node("div");
    const resultMeta = node("span");
    let filterBar;
    const drawMatches = () => {
      const rows = data.items.filter(match => {
        const status = matchPublicStatus(match);
        const teams = [match.home_team, match.away_team];
        const upcoming = !["Encerrado", "Aguardando resultado"].includes(status);
        const query = selected.search.trim().toLocaleLowerCase("pt-BR");
        const searchable = `${displayTeamName(match.home_team)} ${displayTeamName(match.away_team)} ${match.home_team || ""} ${match.away_team || ""}`.toLocaleLowerCase("pt-BR");
        return (!query || searchable.includes(query))
          && (selected.group === "all" || match.group_name === selected.group)
          && (selected.stage === "all" || match.stage === selected.stage)
          && (selected.team === "all" || teams.includes(selected.team))
          && (selected.date === "all" || match.local_date === selected.date)
          && (selected.status === "all" || status === selected.status || (selected.status === "Próximos" && upcoming));
      });
      resultMeta.textContent = `${rows.length} ${rows.length === 1 ? "partida" : "partidas"}`;
      calendarHost.replaceChildren(rows.length ? matchCalendarGroups(rows, selected.grouping) : emptyState("Nenhuma partida neste recorte", "Ajuste ou limpe os filtros para voltar ao calendário."));
    };
    filterBar = matchFilterBar({ rows: data.items, filters: data.filters || {}, stages: data.stage_distribution || [], selected, onChange: drawMatches });
    const grouping = node("div", { class: "matches-grouping-control", role: "group", "aria-label": "Agrupar calendário" }, [
      node("button", { type: "button", class: "is-active", text: "Por data" }),
      node("button", { type: "button", text: "Por fase" }),
    ]);
    grouping.querySelectorAll("button").forEach((button, index) => button.onclick = () => {
      selected.grouping = index === 0 ? "date" : "stage";
      grouping.querySelectorAll("button").forEach(item => item.classList.toggle("is-active", item === button));
      drawMatches();
    });
    const calendarSection = section("Calendário", "Horários em Brasília", node("div", { class: "matches-calendar-experience" }, [
      node("div", { class: "matches-calendar-toolbar" }, [
        node("label", { class: "matches-search" }, [
          node("span", { text: "Buscar seleção" }),
          node("input", { type: "search", placeholder: "Ex.: Brasil", autocomplete: "off", oninput: event => { selected.search = event.target.value; drawMatches(); } }),
        ]),
        summary.current_phase ? node("button", {
          type: "button", class: "matches-phase-shortcut",
          text: `Só ${String(summary.current_phase).toLocaleLowerCase("pt-BR")}`,
          onclick: event => {
            const active = event.currentTarget.classList.toggle("is-active");
            selected.stage = active ? (data.items.find(match => matchStageLabel(match) === summary.current_phase)?.stage || "all") : "all";
            drawMatches();
          },
        }) : null,
        filterBar, grouping,
      ].filter(Boolean)),
      calendarHost,
    ]), "matches-calendar-section");
    calendarSection.querySelector(".section-heading").append(resultMeta);
    fragment.append(calendarSection);
    drawMatches();
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

  function lineupPositionCode(player, matchPlayer) {
    return positionLabel(resolvedPlayerPosition(matchPlayer || player));
  }

  function lineupPlayerRow(player, className = "", detail = null, matchPlayer = null) {
    const hasJerseyNumber = metricAvailable(player.jersey_number);
    const row = node("li", { class: className }, [
      node("span", { class: `shirt-number${hasJerseyNumber ? "" : " is-unavailable"}`, text: hasJerseyNumber ? player.jersey_number : "" }),
      node("strong", { text: player.name || player.player_name }),
      detail
        ? node("span", { class: "lineup-entry-detail", text: detail })
        : node("span", { text: lineupPositionCode(player, matchPlayer) }),
    ]);
    return makePlayerSurfaceInteractive(row, matchPlayer);
  }

  function lineupUnit(player, matchPlayer) {
    return { GOL: "Goleiro", DEF: "Defesa", MEI: "Meio-campo", ATA: "Ataque" }[lineupPositionCode(player, matchPlayer)] || "Ataque";
  }

  function lineupPanel(side, matchPlayers = [], events = []) {
    if (!side) return null;
    const players = side.starting_xi || [];
    const subs = side.substitutes || [];
    const enteredMinutes = substitutionEntryMinutes(side, events);
    const grouped = new Map();
    players.forEach(player => {
      const matchPlayer = matchLineupPlayer(player, side.team_name, matchPlayers);
      const unit = lineupUnit(player, matchPlayer);
      if (!grouped.has(unit)) grouped.set(unit, []);
      grouped.get(unit).push({ player, matchPlayer });
    });
    return node("article", { class: "lineup-card" }, [
      node("div", { class: "chart-card-head" }, [
        node("p", { class: "eyebrow", text: side.formation ? `Formação ${side.formation}` : "Escalação" }),
        node("h3", {}, side.team_name ? node("button", { type: "button", class: "lineup-team-link", onclick: () => side.team_id && goToProfile("team", side.team_id) }, teamLabel(side.team_name)) : "Equipe"),
      ]),
      node("div", { class: "lineup-units" }, ["Goleiro", "Defesa", "Meio-campo", "Ataque"].filter(unit => grouped.has(unit)).map(unit => node("section", { class: "lineup-unit" }, [
        node("h4", { text: unit }),
        node("ol", { class: "lineup-list" }, grouped.get(unit).map(({ player, matchPlayer }) => lineupPlayerRow(player, "", null, matchPlayer))),
      ]))),
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
    if (type === "goal") return [
      player || "Gol confirmado",
      event?.assist_name ? `assistência de ${event.assist_name}` : null,
      metricAvailable(event?.xg) ? `${formatValue(event.xg)} xG` : null,
    ].filter(Boolean).join(" · ");
    // team_name of an own goal is the benefiting side (fixed in the backend).
    if (type === "own_goal") return [
      player || "Gol contra confirmado",
      event?.team_name ? `a favor de ${displayTeamName(event.team_name)}` : null,
    ].filter(Boolean).join(" · ");
    if (type === "substitution") {
      const incoming = event?.player_in_name || player;
      if (incoming && event?.player_out_name) return `${displayTeamName(event?.team_name)} · ${incoming} entrou no lugar de ${event.player_out_name}`;
      if (incoming) return `${displayTeamName(event?.team_name)} · ${incoming} entrou`;
    }
    if (type === "var") return [
      event?.team_name ? displayTeamName(event.team_name) : null,
      event?.decision || event?.detail || "Revisão registrada",
    ].filter(Boolean).join(" · ");
    if (type === "shot_on_target") return [
      player,
      metricAvailable(event?.xg) ? `${formatValue(event.xg)} xG` : null,
    ].filter(Boolean).join(" · ") || "Finalização no alvo";
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

  // Shared unit-agreement helper: definitions across the product express their unit as a fixed
  // plural noun (e.g. "gols"), since most rankings/labels never show exactly 1 — but ties, small
  // samples and per-match views often do. Centralizing the singular forms here means any list
  // that composes "value + unit" through this helper gets correct agreement for free.
  const UNIT_SINGULAR_FORMS = {
    gols: "gol", chutes: "chute", passes: "passe", ações: "ação",
    desarmes: "desarme", cortes: "corte", duelos: "duelo", defesas: "defesa",
    vermelhos: "vermelho", eventos: "evento",
  };
  function singularizeUnit(value, unit) {
    if (!unit) return unit;
    return Math.abs(value) === 1 && UNIT_SINGULAR_FORMS[unit] ? UNIT_SINGULAR_FORMS[unit] : unit;
  }

  function momentsSummary(rows) {
    const counts = rows.reduce((result, event) => {
      const type = String(event?.type || "").toLowerCase();
      result[type] = (result[type] || 0) + 1;
      return result;
    }, {});
    return [
      pluralCount((counts.goal || 0) + (counts.own_goal || 0), "gol", "gols"),
      pluralCount(counts.shot_on_target, "chute no alvo", "chutes no alvo"),
      pluralCount((counts.yellow_card || 0) + (counts.red_card || 0), "cartão", "cartões"),
      pluralCount(counts.substitution, "substituição", "substituições"),
      pluralCount(counts.var, "revisão do VAR", "revisões do VAR"),
      pluralCount(counts.penalty, "pênalti", "pênaltis"),
    ].filter(Boolean).join(" · ");
  }

  function reconciledMatchEvents(rows, match) {
    const events = [...(rows || [])];
    const isGoalType = event => ["goal", "own_goal"].includes(String(event?.type).toLowerCase());
    const goalMinutes = new Set(events
      .filter(isGoalType)
      .map(event => number(event?.minute))
      .filter(minute => minute !== null));
    (match?.goals || []).forEach(goal => {
      const minute = number(goal?.minute);
      const existing = events.find(event => isGoalType(event) && number(event?.minute) === minute);
      if (existing) {
        if (!metricAvailable(existing.xg) && metricAvailable(goal.xg)) existing.xg = goal.xg;
        if (!existing.player_name) existing.player_name = goal.player_name;
        if (!existing.team_name) existing.team_name = goal.team_name;
        return;
      }
      events.push({
        minute,
        extra_time: goal?.extra_time,
        type: goal?.is_own_goal ? "own_goal" : "goal",
        team_name: goal?.team_name,
        player_name: goal?.player_name,
        xg: goal?.is_own_goal ? null : goal?.xg,
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
      ["Visão geral", "#match-overview"],
      ["Finalizações & xG", "#match-finalizations"],
      ["Jogadores", "#match-players"],
      ["Momentos", "#match-moments"],
      ["Escalações", "#match-lineups"],
    ];
    return node("nav", { class: "match-subnav", "aria-label": "Navegação da partida" }, links.map(([labelText, href], index) =>
      node("a", { class: `match-subnav-link${index === 0 ? " is-active" : ""}`, href, text: labelText, onclick: event => {
        event.preventDefault();
        document.querySelector(href)?.scrollIntoView({ behavior: "smooth", block: "start" });
      } })
    ));
  }

  function activateMatchSubnav(nav) {
    state.matchSubnavObserver?.disconnect();
    const links = [...nav.querySelectorAll(".match-subnav-link")];
    const sections = links.map(link => document.querySelector(link.getAttribute("href"))).filter(Boolean);
    if (!sections.length || !("IntersectionObserver" in window)) return;
    state.matchSubnavObserver = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      links.forEach(link => link.classList.toggle("is-active", link.getAttribute("href") === `#${visible.target.id}`));
    }, { rootMargin: "-18% 0px -68% 0px", threshold: [0, .2, .5] });
    sections.forEach(sectionNode => state.matchSubnavObserver.observe(sectionNode));
  }

  function matchStoryPanel(story = []) {
    const shown = story.slice(0, 5);
    return node("article", { class: "story-card" }, story.length
      ? [
        node("ul", { class: "story-list" }, shown.map(line => node("li", { text: translateTeamsInText(line) }))),
        story.length > shown.length ? node("p", { class: "story-more", text: `+ ${story.length - shown.length} destaque${story.length - shown.length === 1 ? "" : "s"} não exibido${story.length - shown.length === 1 ? "" : "s"}.` }) : null,
      ].filter(Boolean)
      : node("p", { text: "A história da partida aparecerá quando houver estatísticas suficientes." })
    );
  }

  const LOWER_IS_BETTER_METRICS = ["fouls", "yellow_cards", "red_cards", "big_chances_missed", "offsides", "dispossessed"];

  function comparisonBars(rows, className = "", kits = null) {
    if (!rows?.length) return emptyState("Visão geral indisponível", "As métricas comparativas ainda não estão disponíveis para esta partida.");
    return node("div", { class: `comparison-stack ${className}`.trim() }, rows.map(row => {
      const lowerIsBetter = LOWER_IS_BETTER_METRICS.includes(row.metric);
      const title = `${metricName(row.metric)} · ${displayTeamName(row.home_team)}: ${formatValue(row.home_value)} · ${displayTeamName(row.away_team)}: ${formatValue(row.away_value)}${lowerIsBetter ? " · Menor é melhor" : ""}`;
      return node("div", {
        class: `comparison-row${lowerIsBetter ? " is-lower-better" : ""}`,
        tabIndex: 0,
        "aria-label": title,
        "data-tooltip": title,
        style: matchPalette(row.home_team, row.away_team, kits),
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

  function overviewCompleteTable(rows) {
    return node("div", { class: "table-wrap overview-complete-table", tabindex: "0", role: "region", "aria-label": "Métricas completas da partida" }, [
      node("table", {}, [
        node("thead", {}, node("tr", {}, [
          node("th", { text: "Métrica" }),
          node("th", { text: displayTeamName(rows[0]?.home_team) }),
          node("th", { text: displayTeamName(rows[0]?.away_team) }),
          node("th", { text: "Leitura" }),
        ])),
        node("tbody", {}, rows.map(row => {
          const lower = LOWER_IS_BETTER_METRICS.includes(row.metric);
          return node("tr", {}, [
            node("th", { scope: "row", text: metricName(row.metric) }),
            node("td", { text: formatValue(row.home_value) }),
            node("td", { text: formatValue(row.away_value) }),
            node("td", { class: "overview-reading", text: lower ? "Menor é melhor" : "Maior valor em destaque" }),
          ]);
        })),
      ]),
    ]);
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
    const kits = matchKits(match);
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
            comparisonBars(metrics, "comparison-stack-compact", kits),
          ])
        ))
      : comparisonBars(rows.slice(0, 10), "", kits);
    return node("div", { class: "match-overview-content" }, [
      node("div", { class: "comparison-team-legend", style: matchPalette(match?.home_team, match?.away_team, kits) }, [
        node("span", {}, [node("i", { class: "legend-dot is-home" }), teamLabel(match?.home_team)]),
        node("span", {}, [node("i", { class: "legend-dot is-away" }), teamLabel(match?.away_team)]),
        node("small", { text: "Em faltas e cartões, menor é melhor." }),
      ]),
      primary,
      rows.length > 10 ? node("details", { class: "overview-disclosure" }, [
        node("summary", {}, [
          node("span", { text: "Ver métricas completas" }),
          node("strong", { text: `${rows.length} indicadores` }),
        ]),
        overviewCompleteTable(rows),
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
    if (player.impact_reasons?.length) return player.impact_reasons.slice(0, 3).join(" · ");
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
      node("p", { class: "section-intro", text: "Índice 0–100 de influência nesta partida, com peso para ações decisivas e contexto da função." }),
      node("div", { class: "card-grid" }, players.slice(0, 3).map((player, index) => {
        const fullPlayer = matchPlayers.find(candidate => candidate.player_id === player.player_id)
          || matchPlayers.find(candidate => candidate.player_name === player.player_name && candidate.team_name === player.team_name);
        const card = node("article", { class: "card impact-card" }, [
          node("span", { class: "card-kicker", text: `#${index + 1}` }),
          node("h3", { text: player.player_name }),
          node("p", { class: "impact-role", text: [player.impact_category, player.team_name ? displayTeamName(player.team_name) : null, resolvedPlayerPosition(player)].filter(Boolean).join(" · ") }),
          node("strong", { class: "impact-inline-score", text: `${formatValue(player.impact_score)}/100` }),
          impactMaxNote(player),
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
    if (!official) return `xG do mapa de chutes: ${byShot}.`;
    const officialValues = Object.fromEntries(teams.map(team => [team, Math.max(0, number(official[team]) || 0)]));
    const differs = teams.some(team => Math.abs(officialValues[team] - shotTotals[team]) >= 0.01);
    if (!differs) return `xG acumulado dos chutes: ${byShot}.`;
    const overview = teams.map(team => `${displayTeamName(team)} ${formatValue(officialValues[team])} xG`).join(" · ");
    return `xG do mapa de chutes: ${byShot}. xG agregado da visão geral: ${overview}. Pequenas diferenças refletem a fonte de cada cálculo.`;
  }

  const PENALTY_RESULT_LABELS = { goal: "Gol", save: "Defendida pelo goleiro", saved: "Defendida pelo goleiro", miss: "Para fora", post: "Na trave" };
  const PENALTY_PHASE_LABELS = { shootout: "Disputa de pênaltis", in_game: "Tempo de jogo" };
  const GOAL_MOUTH_LABELS = {
    low_centre: "Baixa, ao centro", high_centre: "Alta, ao centro",
    low_left: "Baixa, à esquerda", low_right: "Baixa, à direita",
    high_left: "Alta, à esquerda", high_right: "Alta, à direita",
    high: "Por cima do gol", left: "À esquerda, para fora", right: "À direita, para fora",
    close_left: "Rente ao poste esquerdo", close_right: "Rente ao poste direito",
  };

  function penaltyMapPanel(data) {
    const kicks = data.penalties || [];
    if (!kicks.length) return null;
    const match = data.match || {};
    const teams = [match.home_team, match.away_team].filter(name => kicks.some(kick => kick.team_name === name));
    const state = { team: "all", selected: 0 };
    const output = node("div", { class: "penalty-map-body" });
    const kickKey = kick => `${kick.order}`;
    const shootoutScore = metricAvailable(match.penalty_home_score) && metricAvailable(match.penalty_away_score)
      ? `${displayTeamName(match.home_team)} ${formatValue(match.penalty_home_score)}–${formatValue(match.penalty_away_score)} ${displayTeamName(match.away_team)} na disputa por pênaltis`
      : null;
    const filters = node("div", { class: "segmented-control penalty-map-filters" }, [
      ["all", "Todas"], ...teams.map(team => [team, displayTeamName(team)]),
    ].map(([key, labelText]) => node("button", {
      type: "button", text: labelText,
      onclick: event => {
        state.team = key;
        event.currentTarget.parentElement.querySelectorAll("button").forEach(button => button.classList.toggle("is-active", button === event.currentTarget));
        draw();
      },
      class: key === "all" ? "is-active" : "",
    })));
    function filteredKicks() {
      return kicks.filter(kick => state.team === "all" || kick.team_name === state.team);
    }
    const decisiveOrder = (() => {
      const shootout = kicks.filter(kick => kick.phase === "shootout");
      if (!shootout.length || !metricAvailable(match.penalty_home_score) || !metricAvailable(match.penalty_away_score)) return null;
      const winner = number(match.penalty_home_score) > number(match.penalty_away_score) ? match.home_team : match.away_team;
      const winning = shootout.filter(kick => kick.team_name === winner && kick.is_goal);
      return winning.length ? winning[winning.length - 1].order : null;
    })();
    function goalFrame(rows) {
      // Goal frame from the taker's point of view. In the provider data, lower y = the
      // taker's right (validated against goal_mouth_location left/right across the whole
      // edition), so the axis is flipped. Posts at y 44.62/55.38; crossbar at z=35 in the
      // source scale.
      const xFor = value => Math.max(3, Math.min(97, 50 + (50 - value) * 6.9));
      const yFor = value => Math.max(4, 48 - Math.max(0, value) * 0.706);
      const svg = svgNode("svg", { viewBox: "0 0 100 56", class: "penalty-goal-svg", role: "img", "aria-label": `Destino de ${rows.length} cobranças de pênalti, na visão do batedor` });
      const postLeft = xFor(55.38), postRight = xFor(44.62), bar = yFor(35);
      for (let line = 1; line < 6; line += 1) {
        svg.append(svgNode("line", { x1: postLeft + (postRight - postLeft) / 6 * line, y1: bar, x2: postLeft + (postRight - postLeft) / 6 * line, y2: 48, class: "penalty-net" }));
      }
      for (let line = 1; line < 4; line += 1) {
        svg.append(svgNode("line", { x1: postLeft, y1: bar + (48 - bar) / 4 * line, x2: postRight, y2: bar + (48 - bar) / 4 * line, class: "penalty-net" }));
      }
      svg.append(
        svgNode("line", { x1: 0, y1: 48, x2: 100, y2: 48, class: "penalty-ground" }),
        svgNode("path", { d: `M ${postLeft} 48 L ${postLeft} ${bar} L ${postRight} ${bar} L ${postRight} 48`, class: "penalty-frame" }),
      );
      const occupied = new Map();
      rows.forEach(kick => {
        if (kick.goal_mouth_y === null || kick.goal_mouth_y === undefined || kick.goal_mouth_z === null || kick.goal_mouth_z === undefined) return;
        let cx = xFor(number(kick.goal_mouth_y)), cy = yFor(number(kick.goal_mouth_z));
        const cell = `${Math.round(cx / 6)}|${Math.round(cy / 6)}`;
        const bumps = occupied.get(cell) || 0;
        occupied.set(cell, bumps + 1);
        cx = Math.max(4, Math.min(96, cx + bumps * 4.6));
        const teamIndex = kick.team_name === match.away_team ? 1 : 0;
        const selected = kicks.indexOf(kick) === state.selected;
        const group = svgNode("g", {
          transform: `translate(${cx} ${cy})`,
          class: `penalty-kick is-${kick.is_goal ? "goal" : "missed"}${selected ? " is-selected" : ""}`,
          style: `--team-color:${kitColor(matchKits(match), kick.team_name, teamIndex)}`,
          tabindex: "0",
          role: "button",
          "aria-pressed": String(selected),
          "aria-label": `Cobrança ${kick.order}: ${personName(kick)}, ${PENALTY_RESULT_LABELS[String(kick.result || "").toLowerCase()] || "resultado não informado"}`,
        });
        const resultLabel = PENALTY_RESULT_LABELS[String(kick.result || "").toLowerCase()] || "Resultado não informado";
        group.append(svgNode("circle", { r: 3.3, class: "penalty-kick-badge" }));
        attachChartTooltip(group, `Cobrança ${kick.order} · ${personName(kick)} (${displayTeamName(kick.team_name)}) · ${resultLabel}${kick.order === decisiveOrder ? " · Cobrança decisiva" : ""}`);
        if (kick.is_goal) group.append(svgNode("path", { d: "M -1.5 0.1 L -0.5 1.3 L 1.6 -1.2", class: "penalty-kick-glyph" }));
        else if (String(kick.result || "").toLowerCase() === "save") group.append(svgNode("rect", { x: -1.1, y: -1.1, width: 2.2, height: 2.2, class: "penalty-kick-glyph is-filled" }));
        else group.append(svgNode("path", { d: "M -1.3 -1.3 L 1.3 1.3 M -1.3 1.3 L 1.3 -1.3", class: "penalty-kick-glyph" }));
        const select = () => { state.selected = kicks.indexOf(kick); draw(); };
        group.addEventListener("click", select);
        group.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); }
        });
        svg.append(group);
      });
      return svg;
    }
    function kickCard(kick) {
      if (!kick) return null;
      const details = [
        ["Resultado", PENALTY_RESULT_LABELS[String(kick.result || "").toLowerCase()] || "Não informado"],
        ["Destino", GOAL_MOUTH_LABELS[String(kick.goal_mouth_location || "").toLowerCase()] || "Não informado"],
        ["Parte do corpo", BODY_PART_LABELS[String(kick.body_part || "").toLowerCase()] || "Não informada"],
        ["Momento", PENALTY_PHASE_LABELS[kick.phase] || "Não informado"],
        kick.order === decisiveOrder ? ["Peso", "Cobrança decisiva"] : null,
        kick.phase === "in_game" && metricAvailable(kick.xg) ? ["xG", formatValue(kick.xg)] : null,
      ].filter(Boolean);
      return node("article", { class: "penalty-kick-card" }, [
        node("header", {}, [
          flagNode(kick),
          node("span", {}, [node("strong", { text: personName(kick) }), node("small", { text: displayTeamName(kick.team_name) })]),
          node("time", { text: `${formatValue(kick.minute)}'` }),
        ]),
        node("dl", {}, details.map(([labelText, value]) => node("div", {}, [node("dt", { text: labelText }), node("dd", { text: value })]))),
      ]);
    }
    function draw() {
      const rows = filteredKicks();
      if (!rows.some(kick => kicks.indexOf(kick) === state.selected)) state.selected = kicks.indexOf(rows[0]);
      output.replaceChildren(
        node("div", { class: "penalty-goal-wrap" }, [goalFrame(rows), node("p", { class: "penalty-map-caption", text: "Baliza na visão do batedor · ✓ gol · ✕ perdido · ■ defendido · cor = seleção" })]),
        kickCard(kicks[state.selected]),
      );
    }
    draw();
    return node("article", { class: "finalizations-panel penalty-map-panel" }, [
      node("div", { class: "subsection-heading" }, [
        node("h3", { text: kicks.every(kick => kick.phase === "shootout") ? "Disputa de pênaltis" : "Pênaltis da partida" }),
        node("span", { text: `${kicks.length} ${kicks.length === 1 ? "cobrança" : "cobranças"}` }),
      ]),
      shootoutScore ? node("p", { class: "penalty-map-score", text: shootoutScore }) : null,
      node("p", { class: "penalty-map-note", text: "Cobranças da disputa por pênaltis ficam fora do mapa de chutes e do xG da partida; pênaltis no tempo de jogo seguem contando." }),
      filters,
      output,
    ].filter(Boolean));
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
          ? interactiveShotMap(data.shot_map, matchKits(data.match))
          : emptyState("Mapa de chutes ainda não disponível para esta partida."),
      ]),
      penaltyMapPanel(data),
      node("article", { class: "finalizations-panel" }, [
        node("div", { class: "subsection-heading" }, node("h3", { text: "Fluxo de xG" })),
        context ? node("p", { class: "xg-context", text: context }) : null,
        data.xg_flow?.length
          ? xgFlowPlot(data.xg_flow, matchKits(data.match))
          : emptyState("Fluxo de xG ainda não disponível para esta partida."),
      ]),
    ].filter(Boolean));
  }

  function radarChart(profile = [], title = "Radar do jogador", benchmark = [], benchmarkLabel = "Média comparativa", large = false, leader = [], leaderLabel = "Líder") {
    const axes = profile.filter(item => item?.value !== undefined && item?.value !== null);
    if (axes.length < 3) return emptyState("Radar indisponível", "Este jogador ainda não tem dimensões suficientes para uma comparação contextual.");
    const size = large ? 360 : 260;
    const center = size / 2;
    const radius = large ? 116 : 82;
    const axisLabel = axis => RADAR_LABELS[axis?.axis] || RADAR_LABELS[axis?.abbr] || axis?.axis || "Métrica";
    const points = axes.map((axis, index) => {
      const angle = -Math.PI / 2 + index * (Math.PI * 2 / axes.length);
      const valueRadius = radius * Math.max(0, Math.min(100, number(axis.value) || 0)) / 100;
      return {
        axis,
        angle,
        labelX: center + Math.cos(angle) * (radius + (large ? 38 : 28)),
        labelY: center + Math.sin(angle) * (radius + (large ? 38 : 28)),
        x: center + Math.cos(angle) * valueRadius,
        y: center + Math.sin(angle) * valueRadius,
        gridX: center + Math.cos(angle) * radius,
        gridY: center + Math.sin(angle) * radius,
      };
    });
    const benchmarkByAxis = new Map(benchmark.map(axis => [axis.axis, number(axis.value)]));
    const benchmarkPoints = points.map(point => {
      const valueRadius = radius * Math.max(0, Math.min(100, benchmarkByAxis.get(point.axis.axis) ?? 50)) / 100;
      return { ...point, x: center + Math.cos(point.angle) * valueRadius, y: center + Math.sin(point.angle) * valueRadius };
    });
    const leaderByAxis = new Map(leader.map(axis => [axis.axis, number(axis.value)]));
    const hasLeader = points.length > 0 && points.every(point => leaderByAxis.get(point.axis.axis) !== undefined);
    const leaderPoints = hasLeader ? points.map(point => {
      const valueRadius = radius * Math.max(0, Math.min(100, leaderByAxis.get(point.axis.axis))) / 100;
      return { ...point, x: center + Math.cos(point.angle) * valueRadius, y: center + Math.sin(point.angle) * valueRadius };
    }) : [];
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
    if (hasLeader) svg.append(svgNode("polygon", { points: leaderPoints.map(point => `${point.x},${point.y}`).join(" "), class: "radar-leader-line" }));
    if (benchmark.length) svg.append(svgNode("polygon", { points: benchmarkPoints.map(point => `${point.x},${point.y}`).join(" "), class: "radar-benchmark-area" }));
    svg.append(svgNode("polygon", { points: points.map(point => `${point.x},${point.y}`).join(" "), class: "radar-area" }));
    points.forEach(point => {
      const benchmarkValue = benchmarkByAxis.get(point.axis.axis);
      const leaderValue = leaderByAxis.get(point.axis.axis);
      const composition = (point.axis.available_metrics || []).filter(Boolean);
      const tooltip = `${axisLabel(point.axis)}: ${formatValue(point.axis.value)}/100${benchmarkValue !== undefined ? ` · ${benchmarkLabel}: ${formatValue(benchmarkValue)}/100` : ""}${leaderValue !== undefined ? ` · ${leaderLabel}: ${formatValue(leaderValue)}/100` : ""}${composition.length ? ` · Composição: ${composition.join(", ")}` : ""}`;
      const dot = svgNode("circle", { cx: point.x, cy: point.y, r: 3.5, class: "radar-dot", tabindex: "0", "aria-label": tooltip });
      svg.append(attachChartTooltip(dot, tooltip));
    });
    return node("div", { class: "radar-comparison" }, [node("div", { class: "radar-wrap" }, svg), benchmark.length ? node("div", { class: "radar-legend" }, [node("span", { class: "is-selected", text: "Selecionado" }), node("span", { class: "is-benchmark", text: benchmarkLabel }), hasLeader ? node("span", { class: "is-leader", text: leaderLabel }) : null].filter(Boolean)) : null]);
  }

  const metricAvailable = value => value !== null && value !== undefined && value !== "";

  function percentWithVolume(value, numerator, denominator) {
    if (!metricAvailable(value) || !metricAvailable(numerator) || !metricAvailable(denominator) || number(denominator) <= 0) return null;
    return `${formatValue(value)}% (${formatValue(numerator)}/${formatValue(denominator)})`;
  }

  function modalMetric(labelText, value, title = null) {
    if (!metricAvailable(value)) return null;
    return { label: labelText, value: typeof value === "number" ? formatValue(value) : value, title };
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
    if (player.macroposition === "Goleiro") {
      return {
        attackCreation: [],
        passDuelsDiscipline: [
          modalStatSection("Goleiro", [
            modalMetric("Defesas", player.saves),
            modalMetric("Toques", player.touches),
            modalMetric("Cortes", player.clearances),
            modalMetric("Recuperações", player.recoveries),
          ]),
          modalStatSection("Distribuição", passing),
        ].filter(Boolean),
      };
    }
    return {
      attackCreation: [attack, creation].filter(Boolean),
      passDuelsDiscipline: [
        number(player.passes) > 0 ? modalStatSection("Passe", passing) : null,
        duels,
        dribbles,
        discipline,
        defense,
      ].filter(Boolean),
    };
  }

  function playerQuickMetrics(player) {
    const contextual = metricAvailable(player.profile_score) ? `${formatValue(player.profile_score)}/100` : null;
    const base = [
      modalMetric("Minutos", player.minutes_played),
      modalMetric("Perfil contextual", contextual, "Score calculado pelo produto (0–100) para comparar o jogador com outros da mesma função nesta partida. Não é um campo da fonte de dados."),
      modalMetric("Rating", player.rating, "Nota original informada pela TheStatsAPI para esta partida."),
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

  function playerShotMap(shots, { color = null } = {}) {
    const clean = shots
      .map(shot => ({ shot, x: number(shot.x), y: number(shot.y) }))
      .filter(item => item.x !== null && item.y !== null);
    if (!clean.length) return null;
    const width = 100, height = 38;
    const markerSize = xg => Math.max(1, Math.min(2.6, 1 + Math.max(0, xg) * 2.1));
    const jitter = (index, total) => {
      if (total <= 1) return { x: 0, y: 0 };
      const angle = -Math.PI / 2 + index * (Math.PI * 2 / total);
      const radius = Math.min(1.2, 0.45 + total * 0.08);
      return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
    };
    const svg = svgNode("svg", {
      viewBox: `0 0 ${width} ${height}`,
      class: "pitch-svg pitch-svg-crop",
      role: "img",
      "aria-label": `Área de finalização com ${clean.length} finalizações do jogador`,
    });
    svg.append(svgNode("title", {}, "Mapa de finalizações do jogador — área de finalização recortada, gol no topo."));
    for (let band = 0; band < 10; band += 1) {
      svg.append(svgNode("rect", { x: band * 10, y: 0, width: 10, height, class: `pitch-stripe${band % 2 ? " is-alt" : ""}` }));
    }
    svg.append(svgNode("rect", { x: 0, y: 0, width, height, class: "pitch-line pitch-crop" }));
    const markings = [
      ["rect", { x: 20, y: 0, width: 60, height: 16 }],
      ["rect", { x: 37, y: 0, width: 26, height: 5.5 }],
      ["circle", { cx: 50, cy: 10.5, r: 0.7 }],
    ];
    markings.forEach(([tag, attrs]) => svg.append(svgNode(tag, { ...attrs, class: "pitch-line" })));
    svg.append(svgNode("line", { x1: 0, y1: height - .5, x2: width, y2: height - .5, class: "pitch-crop-edge" }));
    const positioned = clean.map(({ shot, x, y }) => {
      const goal = Boolean(shot.is_goal);
      const penalty = isPenaltyShot(shot);
      return {
        shot,
        goal,
        penalty,
        cx: penalty ? 50 : Math.max(1, Math.min(width - 1, y)),
        cy: penalty ? 10.5 : Math.max(1, Math.min(height - 1, x)),
      };
    });
    const clusters = positioned.reduce((map, point) => {
      const key = point.penalty ? `penalty|${shotKey(point.shot)}` : `${Math.round(point.cx * 2) / 2}|${Math.round(point.cy * 2) / 2}`;
      map.set(key, (map.get(key) || 0) + 1);
      point.clusterKey = key;
      return map;
    }, new Map());
    const seen = new Map();
    positioned.forEach(({ shot, goal, penalty, cx, cy, clusterKey }) => {
      const total = clusters.get(clusterKey) || 1;
      const index = seen.get(clusterKey) || 0;
      seen.set(clusterKey, index + 1);
      const offset = penalty ? { x: 0, y: 0 } : jitter(index, total);
      const markerCx = Math.max(1, Math.min(width - 1, cx + offset.x));
      const markerCy = Math.max(1, Math.min(height - 1, cy + offset.y));
      const xg = Math.max(0, number(shot.xg ?? shot.statsbomb_xg) || 0);
      const size = markerSize(xg);
      const colorStyle = color ? { style: `--team-color:${color}` } : {};
      const marker = goal
        ? svgNode("polygon", {
          points: starPoints(markerCx, markerCy, size * 0.95, 0.28),
          class: "shot-point is-player-shot is-goal",
          ...colorStyle,
          tabindex: "0",
          role: "img",
          "aria-label": `${formatValue(shot.minute)}', gol, xG ${formatValue(xg)}, ${shotMatchLabel(shot)}`,
        })
        : svgNode("circle", {
          cx: markerCx, cy: markerCy, r: size,
          class: "shot-point is-player-shot",
          ...colorStyle,
          tabindex: "0",
          role: "img",
          "aria-label": `${formatValue(shot.minute)}', finalização, xG ${formatValue(xg)}, ${shotMatchLabel(shot)}`,
        });
      const outcome = SHOT_OUTCOME_LABELS[String(shot.shot_outcome || "").toLowerCase()] || (goal ? "Gol" : "Finalização");
      const bodyPart = BODY_PART_LABELS[String(shot.body_part || "").toLowerCase()] || "Parte do corpo não informada";
      const shotType = SHOT_TYPE_LABELS[String(shot.shot_type || "").toLowerCase()] || "Situação não informada";
      const tooltip = `Minuto ${formatValue(shot.minute)} · ${shotMatchLabel(shot)} · adversário: ${shotOpponentName(shot)} · xG ${formatValue(xg)} · ${outcome} · ${bodyPart} · ${shotType}`;
      svg.append(attachChartTooltip(marker, tooltip));
    });
    return node("div", { class: "pitch-wrap player-pitch-wrap" }, [
      svg,
      node("div", { class: "chart-legend" }, [
        node("span", { class: "shot-symbol-legend", text: "Círculo = chute · Estrela = gol · Tamanho = xG" }),
      ]),
    ]);
  }

  const SHOT_RESULT_TO_EVENT_TYPE = { save: "shot_on_target", block: "shot_blocked", miss: "shot_off_target", post: "shot_post" };

  function playerTimelineEntries(player) {
    const shotEntries = (player.player_shots || []).map(shot => {
      const outcome = String(shot.shot_outcome || "").toLowerCase();
      return {
        kind: "shot",
        minute: number(shot.minute),
        type: shot.is_goal ? "goal" : (SHOT_RESULT_TO_EVENT_TYPE[outcome] || "shot_on_target"),
        shot,
      };
    });
    const eventEntries = sortedEvents(player.player_events || []).map(event => ({
      kind: "event",
      minute: number(event.minute),
      type: String(event.type || "").toLowerCase(),
      event,
    }));
    return [...shotEntries, ...eventEntries].sort((a, b) => (a.minute ?? 0) - (b.minute ?? 0));
  }

  function playerTimelineDescription(entry, player) {
    if (entry.kind === "shot") {
      const shot = entry.shot;
      return [
        metricAvailable(shot.xg) ? `${formatValue(shot.xg)} xG` : null,
        shot.body_part ? (BODY_PART_LABELS[String(shot.body_part).toLowerCase()] || shot.body_part) : null,
      ].filter(Boolean).join(" · ") || null;
    }
    const event = entry.event;
    if (entry.type === "substitution") {
      const isIncoming = event.player_in_name === player.player_name;
      if (isIncoming && event.player_out_name) return `Entrou no lugar de ${event.player_out_name}`;
      if (!isIncoming && event.player_in_name) return `Saiu, entrou ${event.player_in_name}`;
      return isIncoming ? "Entrou em campo" : "Substituído";
    }
    if (entry.type === "var") return event?.decision || event?.detail || "Revisão registrada";
    return null;
  }

  function shotSummary(shots) {
    if (!shots.length) return null;
    const goals = shots.filter(shot => shot.is_goal).length;
    const xg = Math.round(shots.reduce((total, shot) => total + Math.max(0, number(shot.xg ?? shot.statsbomb_xg) || 0), 0) * 100) / 100;
    const conversion = shots.length ? Math.round(goals / shots.length * 1000) / 10 : 0;
    const xgPerShot = shots.length ? Math.round(xg / shots.length * 100) / 100 : 0;
    const items = [
      modalMetric("Finalizações", shots.length),
      modalMetric("Gols", goals),
      modalMetric("xG", xg),
      modalMetric("Conversão", `${formatValue(conversion)}%`),
      modalMetric("xG por finalização", xgPerShot),
    ].filter(Boolean);
    if (!items.length) return null;
    return node("dl", { class: "player-shot-summary" }, items.map(metric =>
      node("div", {}, [node("dt", { text: metric.label }), node("dd", { text: metric.value })])
    ));
  }

  function playerActionsPanel(player) {
    const entries = playerTimelineEntries(player);
    const map = playerShotMap(player.player_shots || []);
    if (!entries.length && !map) return null;
    return node("section", { class: "player-modal-section player-actions-section" }, [
      node("h3", { text: "Finalizações e momentos" }),
      map,
      map ? shotSummary(player.player_shots || []) : null,
      entries.length ? node("ol", { class: "event-timeline player-event-timeline" }, entries.map(entry => node("li", {
        class: `event-item event-${entry.type.replace(/[^a-z0-9_-]/g, "")}`,
      }, [
        node("time", { text: `${formatValue(entry.minute)}'` }),
        node("span", { class: "event-icon", text: EVENT_ICONS[entry.type] || "·", "aria-hidden": "true" }),
        node("div", { class: "event-copy" }, [
          node("strong", { text: EVENT_LABELS[entry.type] || "Lance da partida" }),
          (() => { const description = playerTimelineDescription(entry, player); return description ? node("span", { text: description }) : null; })(),
        ]),
      ]))) : null,
    ].filter(Boolean));
  }

  function playerModalTabDefinitions(sections, hasActionsPanel) {
    return [
      ["resumo", "Resumo"],
      sections.attackCreation.length ? ["ataque_criacao", "Ataque & Criação"] : null,
      sections.passDuelsDiscipline.length ? ["passe_duelos_disciplina", "Passe, Duelos & Disciplina"] : null,
      hasActionsPanel ? ["finalizacoes", "Finalizações"] : null,
    ].filter(Boolean);
  }

  function openPlayerModal(player) {
    document.querySelector(".player-modal")?.remove();
    const entry = (player.player_events || []).find(event => String(event.type).toLowerCase() === "substitution");
    const quickMetrics = playerQuickMetrics(player);
    const minutesWarning = number(player.minutes_played) < 30;
    const sections = playerDetailedSections(player);
    const highlights = playerPerformanceHighlights(player);
    const actionsPanel = playerActionsPanel(player);
    const tabDefinitions = playerModalTabDefinitions(sections, Boolean(actionsPanel));
    let activeTab = tabDefinitions[0]?.[0] || "resumo";
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
    const tabsNav = attachTabListKeyNav(node("div", { class: "player-modal-tabs", role: "tablist" }));
    const tabContent = node("div", { class: "player-modal-tab-content" });
    const renderTabsNav = () => {
      tabsNav.replaceChildren(...tabDefinitions.map(([key, labelText]) => node("button", {
        type: "button", role: "tab", class: key === activeTab ? "is-active" : "",
        "aria-selected": String(key === activeTab), text: labelText,
        onclick: () => {
          activeTab = key; renderTabsNav(); renderTabContent();
          const shell = dialog.querySelector(".player-modal-shell");
          if (shell) shell.scrollTop = 0;
        },
      })));
    };
    const renderTabContent = () => {
      const panels = {
        resumo: [
          node("section", { class: "player-modal-section" }, [
            node("h3", { text: "Resumo da atuação" }),
            node("dl", { class: "player-quick-grid" }, quickMetrics.map(metric => node("div", { title: metric.title }, [node("dt", { text: metric.label }), node("dd", { text: metric.value })]))),
          ]),
          node("section", { class: "player-modal-section" }, [
            node("div", { class: "player-modal-section-head" }, [
              node("h3", { title: "Score calculado pelo produto para comparar o jogador com outros da mesma função — diferente do Rating, que é o campo original da fonte de dados.", text: "Perfil contextual" }),
              node("span", { text: player.macroposition || "Função" }),
            ]),
            playerRadarPanel(player),
          ]),
          highlights,
        ].filter(Boolean),
        ataque_criacao: [node("div", { class: "player-modal-section-grid" }, sections.attackCreation)],
        passe_duelos_disciplina: [node("div", { class: "player-modal-section-grid" }, sections.passDuelsDiscipline)],
        finalizacoes: actionsPanel ? [actionsPanel] : [],
      };
      tabContent.replaceChildren(...(panels[activeTab] || []));
    };
    renderTabsNav();
    renderTabContent();
    const content = [
      node("header", { class: "player-modal-header" }, [
        node("div", { class: "player-modal-identity" }, [
          flagNode(player, "flag-large"),
          node("div", {}, [
            node("p", { class: "eyebrow", text: player.opponent_name ? `${displayTeamName(player.team_name)} vs ${displayTeamName(player.opponent_name)}` : displayTeamName(player.team_name) }),
            node("h2", { id: "player-modal-title", text: player.player_name }),
            node("p", { class: "player-modal-role", text: resolvedPlayerPosition(player) }),
          ]),
        ]),
        closeButton,
        headerFacts.length ? node("p", { class: "player-modal-facts", text: headerFacts.join(" · ") }) : null,
        node("p", { class: "player-modal-story", text: playerPerformanceStory(player) }),
      ]),
      minutesWarning ? node("p", { class: "player-modal-warning", text: "Poucos minutos: interprete o perfil com cautela." }) : null,
      tabsNav,
      tabContent,
      player.player_id ? node("footer", { class: "player-modal-notes" }, node("button", {
        type: "button",
        class: "action-link",
        text: "Ver perfil completo",
        onclick: () => { close(); goToProfile("player", player.player_id); },
      })) : null,
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
    // Fewer columns by default; the toggle reveals the whole set.
    let showAllColumns = false;
    const CORE_COLUMNS = new Set(["player_name", "team_name", "position", "minutes_played", "impact_score", "goals", "xg", "rating"]);
    const allColumns = [
      { key: "player_name", label: "Jogador", value: player => player.player_name, render: player => node("span", {
        class: "player-name-button",
        text: player.player_name,
      }) },
      { key: "team_name", label: "Time", value: player => displayTeamName(player.team_name), render: player => teamLabel(player.team_name) },
      { key: "position", label: "Pos.", value: player => resolvedPlayerPosition(player, true) },
      { key: "minutes_played", label: "Min.", value: player => number(player.minutes_played) },
      { key: "impact_score", label: "Impacto", value: player => number(player.impact_score) },
      { key: "goals", label: "Gols", value: player => number(player.goals) },
      { key: "xg", label: "xG", value: player => number(player.xg) },
      { key: "xa", label: "xA", value: player => number(player.xa) },
      { key: "accurate_passes", label: "Passes", value: player => number(player.accurate_passes) },
      { key: "defensive_actions", label: "Ações defensivas", value: player => defensiveActions(player) },
      { key: "rating", label: "Rating", value: player => number(player.rating) },
    ];
    const columns = () => showAllColumns ? allColumns : allColumns.filter(column => CORE_COLUMNS.has(column.key));
    const columnsToggle = node("button", {
      type: "button", class: "action-link player-columns-toggle", text: "Estatísticas completas",
      onclick: event => {
        showAllColumns = !showAllColumns;
        event.currentTarget.textContent = showAllColumns ? "Menos colunas" : "Estatísticas completas";
        drawHeader(); drawRows();
      },
    });
    const table = node("div", { class: "table-wrap player-table-wrap", tabindex: "0", role: "region", "aria-label": "Tabela de jogadores da partida" }, [
      node("table", { class: "player-metrics-table" }, [
        thead,
        tbody,
      ]),
    ]);

    function sortedRows() {
      const column = allColumns.find(item => item.key === sort.key) || allColumns[0];
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
      thead.replaceChildren(node("tr", {}, columns().map(column => {
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
            node("span", { class: "pill", text: resolvedPlayerPosition(selected) }),
          ]),
          node("strong", { class: "impact-score", text: `${formatValue(selected.impact_score)}/100` }),
          impactMaxNote(selected),
        ]),
        radarChart(selected.radar || [], `${selected.player_name} na partida`),
        node("p", { class: "player-summary", text: playerSummary(selected) }),
        node("div", { class: "player-detail-actions" }, [
          node("button", { type: "button", class: "action-link", text: "Ver estatísticas completas", onclick: () => openPlayerModal(selected) }),
          selected.player_id ? node("button", { type: "button", class: "action-link", text: "Ver perfil completo", onclick: () => goToProfile("player", selected.player_id) }) : null,
        ]),
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
        }, columns().map(column => column.render
          ? node("td", { "data-label": column.label }, column.render(player))
          : node("td", { "data-label": column.label, text: formatValue(column.value(player)) })
        ));
        tr.tabIndex = 0;
        tr.setAttribute("role", "button");
        tr.setAttribute("aria-label", `Selecionar ${player.player_name}; clique duas vezes para abrir o perfil`);
        tr.addEventListener("click", () => {
          selected = player;
          drawRows();
          drawDetail();
        });
        tr.addEventListener("dblclick", () => goToProfile("player", player.player_id));
        tr.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            selected = player;
            drawRows();
            drawDetail();
          }
        });
        return tr;
      }));
    }

    drawHeader();
    drawRows();
    drawDetail();
    return node("div", { class: "player-explorer" }, [node("div", { class: "player-table-tools" }, columnsToggle), withHorizontalScrollFade(table, { wrapClass: "player-table-scroll-wrap", bg: "var(--surface)" }), detail]);
  }

  function interactiveShotMap(rows = [], kits = null) {
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
          kits,
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
    const subnav = matchSubnav();
    fragment.append(matchCenterHero(match));
    fragment.append(subnav);
    const message = first(data, ["notice", "message", "warning"]);
    if (message && !technicalTextPattern.test(message)) fragment.append(node("aside", { class: "notice", text: message }));
    const storyLines = metricAvailable(match?.penalty_home_score) && metricAvailable(match?.penalty_away_score)
      ? [`${penaltyVerdict(match)}, após ${formatValue(match.home_score)}–${formatValue(match.away_score)} no tempo normal e prorrogação.`, ...(data.match_story || [])]
      : data.match_story || [];
    fragment.append(section("História do jogo", null, matchStoryPanel(storyLines), "", "match-summary"));
    if (data.player_impacts?.length) {
      fragment.append(section("Top impactos da partida", null, impactPanel(data.player_impacts, data.players || [])));
    }
    fragment.append(section("Visão geral da partida", null, matchOverview(data, match), "wide-chart match-overview", "match-overview"));
    fragment.append(section("Finalizações & xG", null, finalizationsPanel(data, match), "wide-chart finalizations-section", "match-finalizations"));
    fragment.append(section("Jogadores da partida", null, playerExplorer(data.players || []), "wide-chart", "match-players"));
    fragment.append(section("Momentos do jogo", null, matchMoments(data.events || [], match), "", "match-moments"));
    const lineups = [
      lineupPanel(data.lineups?.home, data.players || [], data.events || []),
      lineupPanel(data.lineups?.away, data.players || [], data.events || []),
    ].filter(Boolean);
    if (lineups.length) fragment.append(section("Escalações", "Titulares e banco", node("div", { class: "lineup-grid" }, lineups), "", "match-lineups"));
    els.view.replaceChildren(fragment);
    activateMatchSubnav(subnav);
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
    // Clicking a match goes straight to the full match page — the summary drawer only
    // remains as a fallback for rows that don't carry a match_id (undefined bracket slots).
    if (match?.match_id) {
      routeTo("matches", match.match_id);
      return;
    }
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
        goToProfile("team", teamId);
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

  function competitionGroupStatus(team, position) {
    if (!state.competitionData?.group_stage_complete) {
      return team.classification_status || (position === 3 ? "Possível vaga" : "Fora agora");
    }
    if (position <= 2) return "Classificado";
    const qualifiedThirds = new Set((state.competitionData.best_thirds || []).slice(0, 8).map(item => item.team_id));
    if (position === 3 && qualifiedThirds.has(team.team_id)) return "Classificado como melhor terceiro";
    return "Eliminado";
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
            node("small", { text: competitionGroupStatus(team, number(position) || index + 1) }),
          ]),
          ...stats.map(([statKey, value]) => node("td", {
            class: statKey === "Pts" ? "competition-points" : "",
          }, statCellButton(team, group.matches || [], statKey, value))),
        ]);
      })),
    ]));
  }

  function competitionKickoffLabel(value) {
    const date = new Date(value || "");
    if (Number.isNaN(date.getTime())) return "Horário a definir";
    const timezone = "America/Sao_Paulo";
    const dateKey = input => new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
    }).format(input);
    const now = new Date();
    const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
    const time = new Intl.DateTimeFormat("pt-BR", { timeZone: timezone, hour: "2-digit", minute: "2-digit" }).format(date);
    if (dateKey(date) === dateKey(now)) return `Hoje · ${time}`;
    if (dateKey(date) === dateKey(tomorrow)) return `Amanhã · ${time}`;
    const dayMonth = new Intl.DateTimeFormat("pt-BR", { timeZone: timezone, day: "2-digit", month: "short" })
      .format(date).replace(" de ", " ").replace(".", "");
    return `${dayMonth} · ${time}`;
  }

  function competitionMatchStatus(match) {
    const status = String(match?.status || "").toLocaleLowerCase("pt-BR");
    const kickoff = new Date(match?.match_date || match?.kickoff_at || "");
    const isStale = !Number.isNaN(kickoff.getTime()) && Date.now() - kickoff.getTime() > 4 * 60 * 60 * 1000;
    const hasScore = match?.home_score !== null && match?.home_score !== undefined
      && match?.away_score !== null && match?.away_score !== undefined;
    if (/live|ao vivo|in progress/.test(status)) {
      if (homeMatchIsLive(match)) return "Ao vivo";
      return hasScore && isStale ? "Encerrado" : "Aguardando resultado";
    }
    if (/finished|finalizado|encerrado/.test(status)) return "Encerrado";
    if (isStale && !hasScore) return "Aguardando resultado";
    return match?.match_id ? "Agendado" : "A definir";
  }

  function competitionMatchRow(match) {
    const statusLabel = competitionMatchStatus(match);
    const isLive = statusLabel === "Ao vivo";
    const isFinished = statusLabel === "Encerrado";
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
        node("time", { dateTime: match?.match_date || "", title: "Horários em Brasília", text: competitionKickoffLabel(match?.match_date) }),
        node("span", { class: isLive ? "live-label" : "competition-match-status", text: statusLabel }),
      ]),
      node("div", { class: "competition-match-score" }, [
        competitionTeamLink(match?.home_team, match?.home_team_id),
        node("strong", { text: score }),
        competitionTeamLink(match?.away_team, match?.away_team_id),
      ]),
      match?.matchday ? node("small", { class: "competition-matchday", text: `Rodada ${formatValue(match.matchday)}` }) : null,
    ]);
    if (match?.match_id) {
      row.addEventListener("click", () => routeTo("matches", match.match_id));
      row.addEventListener("keydown", event => {
        if (event.key === "Enter") {
          event.preventDefault();
          routeTo("matches", match.match_id);
        }
      });
    }
    return row;
  }

  function groupTag(letter) {
    return letter ? node("span", { class: "group-tag", "data-group": letter, text: `Grupo ${letter}` }) : null;
  }

  function competitionGroupCard(group, onToggle) {
    const toggle = node("button", {
      type: "button",
      class: "competition-group-toggle",
      "aria-expanded": "false",
      onclick: () => onToggle(group, toggle),
    }, [
      node("span", { text: "Ver jogos do grupo" }),
      node("strong", { text: `${(group.matches || []).length} jogos` }),
      node("span", { class: "competition-chevron", text: "⌄", "aria-hidden": "true" }),
    ]);
    return node("article", { class: "competition-group-card", id: `grupo-${group.name}`, "data-group": group.name }, [
      node("header", { class: "competition-group-head" }, [
        node("div", {}, [node("p", { class: "eyebrow", text: "Fase de grupos" }), node("h3", { text: `Grupo ${group.name}` })]),
        node("span", { text: "Pts · SG · GP · GC · Campanha" }),
      ]),
      competitionGroupTable(group),
      toggle,
    ]);
  }

  function competitionGroupGamesPanel(group, onClose) {
    return node("section", { class: "competition-group-games-panel", "aria-label": `Jogos do Grupo ${group.name}` }, [
      node("header", {}, [
        node("span", {}, [
          node("small", { text: "Calendário e resultados" }),
          node("h3", { text: `Jogos do Grupo ${group.name}` }),
        ]),
        node("button", { type: "button", class: "competition-group-close", title: "Fechar", "aria-label": `Fechar jogos do Grupo ${group.name}`, text: "×", onclick: onClose }),
      ]),
      node("div", { class: "competition-group-matches" }, (group.matches || []).map(competitionMatchRow)),
    ]);
  }

  function competitionGroupRow(groups) {
    const row = node("div", { class: "competition-group-row" });
    const panelHost = node("div", { class: "competition-group-panel-host", hidden: true });
    let activeGroup = null;
    let activeToggle = null;
    const close = () => {
      activeToggle?.setAttribute("aria-expanded", "false");
      activeToggle?.closest(".competition-group-card")?.classList.remove("is-expanded");
      activeGroup = null;
      activeToggle = null;
      panelHost.hidden = true;
      panelHost.replaceChildren();
    };
    const toggle = (group, button) => {
      if (activeGroup === group.name) { close(); return; }
      close();
      activeGroup = group.name;
      activeToggle = button;
      button.setAttribute("aria-expanded", "true");
      button.closest(".competition-group-card")?.classList.add("is-expanded");
      panelHost.replaceChildren(competitionGroupGamesPanel(group, close));
      panelHost.hidden = false;
    };
    row.append(...groups.map(group => competitionGroupCard(group, toggle)), panelHost);
    return row;
  }

  function bestThirdsTable(rows) {
    const headers = ["Rank", "Grupo", "Seleção", "J", "Pts", "SG", "GP", "Status"];
    return node("div", { class: "competition-table-scroll" }, node("table", { class: "best-thirds-table" }, [
      node("thead", {}, node("tr", {}, headers.map(header => node("th", { text: header, scope: "col" })))),
      node("tbody", {}, rows.map(team => {
        const rank = number(team.rank) || 0;
        const status = team.status || (state.competitionData?.group_stage_complete
          ? rank <= 8 ? "Classificado" : "Eliminado"
          : rank <= 7 ? "Dentro no momento" : rank === 8 ? "Última vaga" : "Fora agora");
        const className = rank <= 7 ? "competition-row-qualified" : rank === 8 ? "competition-row-third" : "competition-row-out";
        return node("tr", { class: className }, [
          node("td", { class: "competition-position", text: `${rank}º` }),
          node("td", {}, team.group_name ? groupTag(team.group_name) : node("span", { text: "—" })),
          node("td", { class: "competition-team-cell" }, competitionTeamLink(rawTeamName(team), team.team_id)),
          node("td", { text: formatValue(team.played) }),
          node("td", { class: "competition-points", text: formatValue(team.points) }),
          node("td", { text: signedStandingValue(team.goal_difference) }),
          node("td", { text: formatValue(team.goals_for) }),
          node("td", {}, node("span", { class: "competition-status", text: status })),
        ]);
      })),
    ]));
  }

  function bestThirdsExperience(rows) {
    return node("div", { class: "best-thirds-experience" }, [
      node("div", { class: "best-thirds-context" }, [
        node("p", { text: "As 8 melhores seleções em 3º lugar avançam para a Fase de 32." }),
        node("p", { text: "Critério exibido: pontos, saldo de gols e gols pró." }),
        node("small", { text: "Critérios adicionais podem depender de regras oficiais não exibidas aqui." }),
      ]),
      bestThirdsTable(rows),
    ]);
  }

  function knockoutTeam(side, winnerName = null) {
    if (side?.defined) {
      const team = competitionTeamLink(side.team_name, side.team_id, `knockout-team${side.team_name === winnerName ? " is-winner" : ""}`);
      return team;
    }
    const placeholder = translateTeamsInText(side?.placeholder || "A definir");
    return node("span", { class: "knockout-team is-placeholder", text: placeholder, title: placeholder });
  }

  function knockoutMatchCard(match) {
    const hasScore = match?.home_score !== null && match?.home_score !== undefined
      && match?.away_score !== null && match?.away_score !== undefined;
    const status = competitionMatchStatus(match);
    const penaltyHome = number(match?.penalty_home_score);
    const penaltyAway = number(match?.penalty_away_score);
    let resultNote = null;
    if (match?.decided_by === "penalties" && match?.winner_name) {
      const homeWon = match.winner_name === match?.home?.team_name;
      const winnerPenalties = homeWon ? penaltyHome : penaltyAway;
      const loserPenalties = homeWon ? penaltyAway : penaltyHome;
      resultNote = winnerPenalties !== null && loserPenalties !== null
        ? `${displayTeamName(match.winner_name)} venceu nos pênaltis por ${formatValue(winnerPenalties)}–${formatValue(loserPenalties)}`
        : `${displayTeamName(match.winner_name)} avançou nos pênaltis`;
    } else if (match?.winner_name) {
      resultNote = `${displayTeamName(match.winner_name)} classificado`;
    }
    const card = node("article", {
      class: `knockout-match${match?.match_id ? " is-clickable" : ""}${match?.decided_by === "penalties" ? " is-penalties" : ""}`,
      role: match?.match_id ? "link" : null,
      tabIndex: match?.match_id ? 0 : -1,
    }, [
      node("div", { class: "knockout-match-meta" }, [
        node("time", { dateTime: match?.kickoff_at || "", title: "Horários em Brasília", text: competitionKickoffLabel(match?.kickoff_at) }),
        node("span", { text: match?.decided_by === "penalties" ? "Pênaltis" : status }),
      ]),
      node("div", { class: "knockout-match-line" }, [
        node("div", { class: `knockout-side${match?.home?.team_name === match?.winner_name ? " is-winner" : ""}` }, knockoutTeam(match?.home, match?.winner_name)),
        hasScore
          ? scoreText(match.home_score, match.away_score, { homeName: match?.home?.team_name, awayName: match?.away?.team_name })
          : node("strong", { class: "knockout-center", text: "×" }),
        node("div", { class: `knockout-side${match?.away?.team_name === match?.winner_name ? " is-winner" : ""}` }, knockoutTeam(match?.away, match?.winner_name)),
      ]),
      resultNote ? node("small", { class: "knockout-result-note", text: resultNote }) : null,
    ]);
    if (match?.match_id) {
      card.addEventListener("click", () => routeTo("matches", match.match_id));
      card.addEventListener("keydown", event => {
        if (event.key === "Enter") {
          event.preventDefault();
          routeTo("matches", match.match_id);
        }
      });
    }
    return card;
  }

  function withHorizontalScrollFade(scrollable, { wrapClass = "", bg = "var(--bg)" } = {}) {
    const fade = node("div", { class: "scroll-fade-edge", "aria-hidden": "true", style: `--scroll-fade-bg:${bg}` });
    const wrap = node("div", { class: `scroll-fade-wrap ${wrapClass}`.trim() }, [scrollable, fade]);
    const updateScrollFade = () => {
      const hasMoreToScroll = scrollable.scrollWidth - scrollable.clientWidth - scrollable.scrollLeft > 4;
      wrap.classList.toggle("has-scroll", hasMoreToScroll);
    };
    scrollable.addEventListener("scroll", updateScrollFade, { passive: true });
    window.addEventListener("resize", updateScrollFade, { passive: true });
    requestAnimationFrame(updateScrollFade);
    return wrap;
  }

  function knockoutBoard(knockout) {
    const board = node("div", { class: "knockout-board" }, node("div", { class: "knockout-board-inner" },
      (knockout.rounds || []).map(round => node("section", { class: `knockout-round${round.matches?.length ? "" : " is-empty"}` }, [
        node("header", {}, [node("span", { text: "Fase" }), node("h3", { text: round.name })]),
        round.matches?.length
          ? node("div", { class: "knockout-round-matches" }, round.matches.map(knockoutMatchCard))
          : node("div", { class: "knockout-empty", text: "Fase ainda a definir" }),
      ]))
    ));
    return withHorizontalScrollFade(board, { wrapClass: "knockout-board-wrap" });
  }

  function competitionKnockoutContext(knockout) {
    if (knockout?.notice) return knockout.notice;
    if (knockout?.started) return "Mata-mata em andamento: acompanhe classificados e próximos confrontos.";
    if (knockout?.group_stage_complete) return "Confrontos definidos para a Fase de 32.";
    return "Confrontos serão atualizados conforme a fase de grupos avançar.";
  }


  function competitionStructuralSummary(data, currentPhase) {
    const rounds = (data.knockout || {}).rounds || [];
    const decided = [], undecided = [];
    rounds.forEach(round => (round.matches || []).forEach(match => {
      (match.winner_name ? decided : undecided).push({ ...match, round_name: round.name });
    }));
    const stamp = match => String(match.kickoff_at || match.match_date || "");
    const currentRound = rounds.find(round => round.name === (data.knockout || {}).current_phase)
      || rounds.find(round => (round.matches || []).some(match => !match.winner_name));
    let alive = null;
    if (currentRound) {
      const names = new Set();
      (currentRound.matches || []).forEach(match => {
        if (match.winner_name) names.add(match.winner_name);
        else {
          if (match.home?.defined && match.home.team_name) names.add(match.home.team_name);
          if (match.away?.defined && match.away.team_name) names.add(match.away.team_name);
        }
      });
      alive = names.size || null;
    }
    const lastDecided = decided.filter(stamp).sort((a, b) => stamp(b).localeCompare(stamp(a)))[0];
    const nextMatch = undecided.filter(match => stamp(match) && (match.home?.defined || match.away?.defined)).sort((a, b) => stamp(a).localeCompare(stamp(b)))[0];
    const path = rounds.filter(round => (round.matches || []).some(match => !match.winner_name)).map(round => round.name).join(" → ");
    const cells = [
      ["Fase atual", currentPhase],
      alive ? ["Seleções vivas", `${alive}`] : null,
      lastDecided ? ["Último definido", `${displayTeamName(lastDecided.winner_name)} eliminou ${displayTeamName([lastDecided.home?.team_name, lastDecided.away?.team_name].find(name => name && name !== lastDecided.winner_name))}`] : null,
      nextMatch ? ["Próximo jogo", `${compactMatchSideLabel(nextMatch.home)} x ${compactMatchSideLabel(nextMatch.away)} · ${homeFriendlyKickoff(nextMatch.kickoff_at || nextMatch.match_date)}`] : null,
      path ? ["Caminho até a final", path] : null,
    ].filter(Boolean);
    return node("div", { class: "competition-structural-summary" }, cells.map(([labelText, value]) =>
      node("div", {}, [node("small", { text: labelText }), node("strong", { text: value })])));
  }

  function renderCompetition(data) {
    state.competitionData = data;
    const currentPhase = data.knockout?.current_phase || (data.group_stage_complete ? "Fase de 32" : "Fase de grupos");
    const fragment = dashboardShell("Competição", "Classificação dos grupos, melhores terceiros e caminho até a final.", data);
    const groupsView = node("div", { class: "competition-view", "data-view": "groups" });
    const thirdsView = node("div", { class: "competition-view", "data-view": "thirds", hidden: true });
    const knockoutView = node("div", { class: "competition-view", "data-view": "knockout", hidden: true });
    const tabs = [
      node("button", { type: "button", role: "tab", class: "is-active", text: "Fase de grupos", "aria-selected": "true", "data-view": "groups" }),
      node("button", { type: "button", role: "tab", text: "Melhores terceiros", "aria-selected": "false", "data-view": "thirds" }),
      node("button", { type: "button", role: "tab", text: "Mata-mata", "aria-selected": "false", "data-view": "knockout" }),
    ];
    const navigation = attachTabListKeyNav(node("nav", { class: "section-tabs competition-tabs", role: "tablist", "aria-label": "Navegação interna da competição" }, tabs));

    function selectView(view) {
      const views = { groups: groupsView, thirds: thirdsView, knockout: knockoutView };
      Object.entries(views).forEach(([key, element]) => { element.hidden = key !== view; });
      tabs.forEach(tab => {
        const active = tab.dataset.view === view;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", String(active));
      });
    }
    tabs[0].onclick = () => selectView("groups");
    tabs[1].onclick = () => selectView("thirds");
    tabs[2].onclick = () => selectView("knockout");
    // Com a fase de grupos encerrada, o Mata-mata é o centro da experiência;
    // a escolha manual (?view=groups|thirds|knockout) sempre vence.
    const requestedView = new URLSearchParams(location.search).get("view");
    const defaultView = ["groups", "thirds", "knockout"].includes(requestedView)
      ? requestedView
      : data.group_stage_complete ? "knockout" : "groups";
    if (defaultView !== "groups") selectView(defaultView);
    fragment.append(competitionStructuralSummary(data, currentPhase), navigation);

    if (data.groups?.length) {
      const rows = [];
      for (let index = 0; index < data.groups.length; index += 2) rows.push(competitionGroupRow(data.groups.slice(index, index + 2)));
      const jump = node("div", { class: "group-jump-row", role: "navigation", "aria-label": "Ir para um grupo" }, data.groups.map(group =>
        node("button", { type: "button", text: `Grupo ${group.name}`, onclick: () => document.getElementById(`grupo-${group.name}`)?.scrollIntoView({ behavior: "smooth", block: "start" }) })));
      const digest = node("p", { class: "groups-digest", text: data.group_stage_complete
        ? "Fase de grupos encerrada — classificação mantida como consulta histórica. Os classificados seguem no Mata-mata."
        : "Classificação em disputa: os dois primeiros de cada grupo e os 8 melhores terceiros avançam." });
      groupsView.append(section("Fase de grupos", `${data.groups.length} grupos`, node("div", {}, [digest, jump, node("div", { class: "competition-groups-grid" }, rows)])));
    } else {
      groupsView.append(emptyState("Grupos ainda não disponíveis", "A classificação aparecerá assim que os grupos forem definidos."));
    }
    if (data.best_thirds?.length) {
      thirdsView.append(section("Melhores terceiros", "8 seleções avançam", bestThirdsExperience(data.best_thirds), "best-thirds-section"));
    } else {
      thirdsView.append(emptyState("Melhores terceiros ainda não disponíveis", "A classificação das terceiras colocadas aparecerá com o avanço dos grupos."));
    }

    const knockout = data.knockout || {};
    knockoutView.append(section("Mata-mata", "Caminho até a final", node("div", { class: "knockout-shell" }, [
      node("p", { class: "knockout-notice", text: competitionKnockoutContext(knockout) }),
      knockoutBoard(knockout),
    ])));
    fragment.append(groupsView, thirdsView, knockoutView);
    els.view.replaceChildren(fragment);
  }

  function renderProfile(data) {
    if (!data.available) {
      els.view.replaceChildren(emptyState("Perfis indisponíveis", data.notice || "Ainda não há dados individuais para esta edição."));
      return;
    }
    const params = new URLSearchParams(location.search);
    let mode = ["team", "compare"].includes(params.get("type")) ? params.get("type") : "player";
    const initialId = params.get("id");
    const fragment = dashboardShell("Perfil", "Análises individuais adaptadas ao tipo e à função selecionada.", data);
    const content = node("div", { class: "profile-mode-content" });
    const tabs = attachTabListKeyNav(node("div", { class: "profile-mode-tabs", role: "tablist", "aria-label": "Tipo de perfil" }, [
      profileModeButton("player", "Jogador"), profileModeButton("team", "Seleção"), profileModeButton("compare", "Comparar"),
    ]));
    function profileModeButton(key, labelText) {
      return node("button", { type: "button", role: "tab", text: labelText, "data-mode": key, onclick: () => { mode = key; history.replaceState(null, "", `${routePath(state.year, "profile")}?type=${key}`); draw(); } });
    }
    function draw() {
      tabs.querySelectorAll("button").forEach(button => { const active = button.dataset.mode === mode; button.classList.toggle("is-active", active); button.setAttribute("aria-selected", String(active)); });
      const isInitialMode = mode === params.get("type");
      content.replaceChildren(
        mode === "player" ? profilePlayerSelector(data.players || [], data.filters || {}, isInitialMode ? initialId : null)
          : mode === "team" ? profileTeamSelector(data.teams || [], isInitialMode ? initialId : null)
            : profileCompareSelector(data, isInitialMode ? { kind: params.get("kind"), a: params.get("a"), b: params.get("b") } : null),
      );
    }
    fragment.append(tabs, content); draw(); els.view.replaceChildren(fragment);
  }

  function profilePlayerTabs(player, shots) {
    const isGoalkeeper = player?.macroposition === "Goleiro" || positionLabel(player?.position) === "GOL";
    return [["general", "Geral"], ...(!isGoalkeeper && shots.length ? [["shots", "Finalizações"]] : []), ["match_log", "Jogo a jogo"]];
  }

  function profilePlayerSelector(players, filters, initialId = null) {
    let selectedId = initialId && players.some(player => player.player_id === initialId) ? initialId : null;
    let selectedData = null, scopeValue = "all", activeTab = "general", token = 0;
    const stateFilters = { search: "", team: "all", positionGroup: "all", inferredPosition: "all" };
    const results = node("div", { class: "profile-selector-results" });
    const detail = node("div", { class: "profile-analysis-host" });
    const selected = node("div", { class: "profile-selected-entity", text: "Escolha um jogador para iniciar a análise." });
    const context = node("select", { disabled: true });
    const tabs = attachTabListKeyNav(node("div", { class: "player-profile-tabs", role: "tablist" }));
    const search = node("input", { type: "search", placeholder: "Buscar jogador", autocomplete: "off" });
    const team = node("select", {}, [node("option", { value: "all", text: "Todas as seleções" }), ...(filters.player_teams || []).map(value => node("option", { value, text: displayTeamName(value) }))]);
    const positionGroup = node("select", {}, [node("option", { value: "all", text: "Todos os grupos" }), ...(filters.position_groups || []).map(value => node("option", { value, text: value }))]);
    const inferredPosition = node("select", {}, [node("option", { value: "all", text: "Todas as posições" }), ...(filters.inferred_positions || []).map(value => node("option", { value, text: value }))]);
    const clear = node("button", { type: "button", class: "profile-clear", text: "Limpar seleção", disabled: true, onclick: clearSelection });
    const panel = node("section", { class: "profile-selector-panel" }, [
      node("div", { class: "profile-selector-fields" }, [node("label", {}, [node("span", { text: "Buscar jogador" }), search]), node("label", {}, [node("span", { text: "Seleção" }), team]), node("label", {}, [node("span", { text: "Grupo bruto" }), positionGroup]), node("label", {}, [node("span", { text: "Posição inferida" }), inferredPosition])]),
      results,
      node("div", { class: "profile-selection-bar" }, [selected, clear]),
      node("div", { class: "profile-context-row" }, [node("label", {}, [node("span", { text: "Recorte da análise" }), context]), tabs]),
    ]);
    function drawResults() {
      const query = stateFilters.search.trim().toLocaleLowerCase("pt-BR");
      const matches = players.filter(player => (!query || `${personName(player)} ${displayTeamName(player.team_name)}`.toLocaleLowerCase("pt-BR").includes(query)) && (stateFilters.team === "all" || player.team_name === stateFilters.team) && (stateFilters.positionGroup === "all" || player.api_position_group === stateFilters.positionGroup) && (stateFilters.inferredPosition === "all" || resolvedPlayerPosition(player) === stateFilters.inferredPosition));
      if (!matches.length) {
        results.replaceChildren(node("p", { class: "profile-selector-empty", text: "Nenhum jogador encontrado com esses filtros." }));
        return;
      }
      const rows = matches.slice(0, 80);
      results.replaceChildren(...rows.map(player => node("button", { type: "button", class: player.player_id === selectedId ? "is-selected" : "", onclick: () => selectPlayer(player) }, [flagNode(player), node("span", {}, [node("strong", { text: personName(player) }), node("small", { text: `${displayTeamName(player.team_name)} · ${resolvedPlayerPosition(player)}` })])])));
      if (matches.length > rows.length) {
        results.append(node("p", { class: "profile-selector-truncated", text: `Mostrando ${rows.length} de ${matches.length} jogadores — refine a busca para ver mais.` }));
      }
    }
    function drawContext() {
      const options = [node("option", { value: "all", text: "Edição inteira" }), node("option", { value: "group_stage", text: "Fase de grupos" }), node("option", { value: "knockout", text: "Mata-mata" })];
      (selectedData?.available_matches || []).forEach(match => options.push(node("option", { value: `match:${match.match_id}`, text: `Jogo: ${translateTeamsInText(match.label)}` })));
      context.replaceChildren(...options); context.value = scopeValue;
    }
    function drawTabs() {
      const player = selectedData?.player || {};
      const definitions = selectedData ? profilePlayerTabs(player, selectedData.shot_map || []) : [];
      if (!definitions.some(([key]) => key === activeTab)) activeTab = "general";
      tabs.replaceChildren(...definitions.map(([key, labelText]) => node("button", { type: "button", role: "tab", class: key === activeTab ? "is-active" : "", text: labelText, "aria-selected": String(key === activeTab), onclick: () => { activeTab = key; drawTabs(); drawDetail(); detail.scrollIntoView({ block: "start" }); } })));
    }
    function drawDetail() {
      if (!selectedId) { detail.replaceChildren(node("p", { class: "profile-empty", text: "Selecione um jogador para ver o perfil individual." })); return; }
      if (!selectedData) { detail.replaceChildren(node("p", { class: "profile-loading", text: "Carregando perfil..." })); return; }
      detail.replaceChildren(playerProfileView(selectedData, activeTab));
    }
    async function load() {
      const current = ++token; selectedData = null; drawDetail();
      const [scope, matchId] = scopeValue.startsWith("match:") ? ["match", scopeValue.slice(6)] : [scopeValue, null];
      const query = new URLSearchParams({ scope }); if (matchId) query.set("match_id", matchId);
      try { const payload = await getJSON(`/editions/${state.year}/players/${encodeURIComponent(selectedId)}?${query}`); if (current !== token) return; selectedData = payload; drawContext(); drawTabs(); drawDetail(); }
      catch (error) { if (error?.name !== "AbortError") detail.replaceChildren(emptyState("Perfil indisponível", "Não foi possível carregar este recorte.")); }
    }
    const swap = node("button", { type: "button", class: "action-link profile-swap", text: "Trocar jogador", hidden: true, onclick: () => { panel.classList.remove("is-collapsed"); swap.hidden = true; search.focus(); } });
    function selectPlayer(player) {
      selectedId = player.player_id; selectedData = null; scopeValue = "all"; activeTab = "general"; clear.disabled = false; context.disabled = false;
      selected.replaceChildren(flagNode(player), node("strong", { text: personName(player) }), node("span", { text: `${displayTeamName(player.team_name)} · ${resolvedPlayerPosition(player)}` }), swap);
      // Escolhido o jogador, o seletor recolhe e o perfil vira o protagonista.
      panel.classList.add("is-collapsed"); swap.hidden = false;
      history.replaceState(null, "", `${routePath(state.year, "profile")}?type=player&id=${encodeURIComponent(selectedId)}`); drawResults(); drawContext(); load();
    }
    function clearSelection() { token += 1; selectedId = null; selectedData = null; clear.disabled = true; context.disabled = true; panel.classList.remove("is-collapsed"); selected.textContent = "Escolha um jogador para iniciar a análise."; history.replaceState(null, "", `${routePath(state.year, "profile")}?type=player`); drawResults(); drawTabs(); drawDetail(); }
    search.oninput = event => { stateFilters.search = event.target.value; drawResults(); }; team.onchange = event => { stateFilters.team = event.target.value; drawResults(); }; positionGroup.onchange = event => { stateFilters.positionGroup = event.target.value; drawResults(); }; inferredPosition.onchange = event => { stateFilters.inferredPosition = event.target.value; drawResults(); }; context.onchange = event => { scopeValue = event.target.value; load(); };
    drawResults(); drawContext(); drawTabs(); drawDetail();
    if (selectedId) selectPlayer(players.find(player => player.player_id === selectedId));
    return node("div", { class: "profile-experience" }, [panel, detail]);
  }

  function teamProfileTabs(data) {
    return [["general", "Geral"], ...(data?.matches?.length ? [["match_log", "Jogo a jogo"]] : []), ...(data?.shot_map?.length ? [["shots", "Finalizações"]] : [])];
  }

  function profileTeamSelector(teams, initialId = null) {
    let selectedId = initialId && teams.some(team => team.team_id === initialId) ? initialId : null, selectedData = null, activeTab = "general", token = 0;
    const results = node("div", { class: "profile-selector-results team-results" });
    const detail = node("div", { class: "profile-analysis-host" });
    const search = node("input", { type: "search", placeholder: "Buscar seleção", autocomplete: "off" });
    const selected = node("div", { class: "profile-selected-entity", text: "Escolha uma seleção para iniciar a análise." });
    const tabs = attachTabListKeyNav(node("div", { class: "player-profile-tabs team-profile-tabs", role: "tablist", "aria-label": "Visualização da seleção" }));
    function drawResults() {
      const query = search.value.trim().toLocaleLowerCase("pt-BR");
      const matches = teams.filter(team => !query || teamName(team).toLocaleLowerCase("pt-BR").includes(query));
      if (!matches.length) {
        results.replaceChildren(node("p", { class: "profile-selector-empty", text: "Nenhuma seleção encontrada com essa busca." }));
        return;
      }
      results.replaceChildren(...matches.map(team => node("button", { type: "button", class: team.team_id === selectedId ? "is-selected" : "", onclick: () => selectTeam(team) }, [flagNode(team), node("span", {}, [node("strong", { text: teamName(team) }), node("small", { text: `${team.group_name ? `Grupo ${team.group_name}` : "Copa 2026"} · ${team.classification_status || "Em disputa"}` })])])));
    }
    function drawTabs() {
      const definitions = selectedData ? teamProfileTabs(selectedData) : [];
      if (!definitions.some(([key]) => key === activeTab)) activeTab = "general";
      tabs.replaceChildren(...definitions.map(([key, labelText]) => node("button", { type: "button", role: "tab", class: key === activeTab ? "is-active" : "", text: labelText, "aria-selected": String(key === activeTab), onclick: () => { activeTab = key; drawTabs(); drawDetail(); detail.scrollIntoView({ block: "start" }); } })));
    }
    function drawDetail() {
      if (!selectedId) { detail.replaceChildren(node("p", { class: "profile-empty", text: "Selecione uma seleção para ver o perfil individual." })); return; }
      if (!selectedData) { detail.replaceChildren(node("p", { class: "profile-loading", text: "Carregando perfil..." })); return; }
      detail.replaceChildren(teamProfileView(selectedData, activeTab));
    }
    const swapTeam = node("button", { type: "button", class: "action-link profile-swap", text: "Trocar seleção", onclick: event => { event.currentTarget.closest(".profile-selector-panel")?.classList.remove("is-collapsed"); search.focus(); } });
    async function selectTeam(team) {
      selectedId = team.team_id; selectedData = null; activeTab = "general"; const current = ++token;
      selected.closest(".profile-selector-panel")?.classList.add("is-collapsed");
      selected.replaceChildren(flagNode(team), node("strong", { text: teamName(team) }), node("span", { text: team.group_name ? `Grupo ${team.group_name}` : "Copa 2026" }), swapTeam);
      history.replaceState(null, "", `${routePath(state.year, "profile")}?type=team&id=${encodeURIComponent(selectedId)}`); drawResults(); drawTabs(); drawDetail();
      try { const payload = await getJSON(`/editions/${state.year}/teams/${encodeURIComponent(selectedId)}`); if (current === token) { selectedData = payload; drawTabs(); drawDetail(); } }
      catch (error) { if (error?.name !== "AbortError") detail.replaceChildren(emptyState("Perfil indisponível", "Não foi possível carregar esta seleção.")); }
    }
    search.oninput = drawResults; drawResults(); if (selectedId) selectTeam(teams.find(team => team.team_id === selectedId));
    drawTabs(); drawDetail();
    const teamPanel = node("section", { class: "profile-selector-panel" }, [node("div", { class: "profile-selector-fields" }, node("label", {}, [node("span", { text: "Buscar seleção" }), search])), results, node("div", { class: "profile-selection-bar" }, [selected, tabs])]);
    if (selectedId) teamPanel.classList.add("is-collapsed");
    return node("div", { class: "profile-experience" }, [teamPanel, detail]);
  }

  function compareAxisChip(labelText, valueA, valueB) {
    return node("span", { class: "insight-evidence", title: `${labelText}: ${formatValue(valueA)}/100 × ${formatValue(valueB)}/100` }, [
      node("strong", { text: `${formatValue(valueA)} × ${formatValue(valueB)}` }),
      node("span", { text: labelText }),
    ]);
  }

  function sharedRadarAxes(a, b) {
    const own = (a.radar || []).filter(axis => metricAvailable(axis.value));
    const other = new Map((b.radar || []).filter(axis => metricAvailable(axis.value)).map(axis => [axis.axis, number(axis.value)]));
    return own.filter(axis => other.has(axis.axis)).map(axis => ({ axis: axis.axis, a: number(axis.value), b: other.get(axis.axis), available_metrics: axis.available_metrics }));
  }

  function playerMatchupInsights(a, b) {
    const pa = a.player || {}, pb = b.player || {};
    const nameA = personName(pa), nameB = personName(pb);
    const shared = sharedRadarAxes(a, b);
    if (!shared.length) {
      return [{
        tag: "Funções diferentes",
        title: "Comparação direta limitada",
        text: `${nameA} e ${nameB} cumprem funções sem eixos estatísticos em comum (caso típico: goleiro contra jogador de linha). Compare cada um dentro da própria função nos perfis individuais.`,
      }];
    }
    const axisName = axis => RADAR_LABELS[axis] || axis;
    const edgesA = shared.filter(item => item.a - item.b >= 12).sort((left, right) => (right.a - right.b) - (left.a - left.b));
    const edgesB = shared.filter(item => item.b - item.a >= 12).sort((left, right) => (right.b - right.a) - (left.b - left.a));
    const balanced = shared.filter(item => Math.abs(item.a - item.b) < 12);
    const listNames = items => items.slice(0, 3).map(item => axisName(item.axis)).join(", ").replace(/, ([^,]*)$/, " e $1");
    const insights = [];
    if (edgesA.length) insights.push({
      side: "a",
      tag: displayTeamName(pa.team_name),
      title: `Onde ${nameA} leva a melhor`,
      text: `Vantagem clara em ${listNames(edgesA)} — território em que ${nameA} supera ${nameB} neste recorte da Copa.`,
      evidence: edgesA.slice(0, 4).map(item => compareAxisChip(axisName(item.axis), item.a, item.b)),
    });
    if (edgesB.length) insights.push({
      side: "b",
      tag: displayTeamName(pb.team_name),
      title: `Onde ${nameB} leva a melhor`,
      text: `Vantagem clara em ${listNames(edgesB)} — território em que ${nameB} supera ${nameA} neste recorte da Copa.`,
      evidence: edgesB.slice(0, 4).map(item => compareAxisChip(axisName(item.axis), item.b, item.a)),
    });
    if (balanced.length) insights.push({
      tag: "Equilíbrio",
      title: "Territórios disputados",
      text: `Em ${listNames(balanced)}, os dois entregam nível parecido — a diferença tende a vir do contexto de equipe, não do repertório individual.`,
      evidence: balanced.slice(0, 4).map(item => compareAxisChip(axisName(item.axis), item.a, item.b)),
    });
    if (!insights.length) insights.push({
      tag: "Equilíbrio",
      title: "Perfis muito próximos",
      text: `${nameA} e ${nameB} apresentam leituras estatísticas quase idênticas neste recorte — escolha entre eles passa por características que os números da Copa ainda não separam.`,
    });
    return insights;
  }

  function teamMatchupInsights(a, b) {
    // One card per rule type: when both sides qualify for the same reading, only the side
    // with the stronger case keeps it — repeated mirrored cards dilute the editorial value.
    const candidates = [];
    const sides = [["a", a, b], ["b", b, a]];
    const scoutingTag = (label, entity) => `${label} de ${teamName(entity.team)}`;
    const balanceA = number(a.benchmarks?.metrics?.xg_difference?.percentile);
    const balanceB = number(b.benchmarks?.metrics?.xg_difference?.percentile);
    if (balanceA !== null && balanceB !== null && Math.abs(balanceA - balanceB) >= 15) {
      const leader = balanceA > balanceB ? a : b;
      const trailer = balanceA > balanceB ? b : a;
      candidates.push({
        key: "campaign",
        strength: 200 + Math.abs(balanceA - balanceB),
        insight: {
          side: balanceA > balanceB ? "a" : "b",
          tag: scoutingTag("Força", leader),
          title: "Vantagem estrutural da campanha",
          text: `Força: saldo de xG superior (${formatValue(leader.team?.xg_difference)} contra ${formatValue(trailer.team?.xg_difference)}). Leitura de scouting: ${teamName(leader.team)} vem criando e cedendo em patamar melhor.`,
        },
      });
    }
    for (const [side, self, other] of sides) {
      const s = key => number(self.benchmarks?.metrics?.[key]?.percentile);
      const o = key => number(other.benchmarks?.metrics?.[key]?.percentile);
      const sv = key => number(self.team?.[key]);
      const ov = key => number(other.team?.[key]);
      const selfName = teamName(self.team), otherName = teamName(other.team);
      const consider = (key, strength, insight) => candidates.push({ key, strength, insight: { side, ...insight } });
      if (s("xg_per_game") !== null && s("xg_per_game") >= 60 && o("xga_per_game") !== null && o("xga_per_game") <= 40) consider("attack_vs_defense", s("xg_per_game") + (100 - o("xga_per_game")), {
        tag: scoutingTag("Força", self),
        title: `Fragilidade explorável de ${otherName}`,
        text: `Força: ${selfName} cria ${formatValue(sv("xg_per_game"))} xG por jogo. Fragilidade explorável: ${otherName} cede ${formatValue(ov("xga_per_game"))} xG por jogo. Caminho: acelerar ataques na área.`,
      });
      if (s("average_possession") !== null && s("average_possession") >= 60 && (s("pass_accuracy") === null || s("pass_accuracy") >= 50) && o("recoveries_per_game") !== null && o("recoveries_per_game") <= 45) consider("control", s("average_possession") + (100 - o("recoveries_per_game")), {
        tag: scoutingTag("Força", self),
        title: `Fragilidade de ${otherName} sem a bola`,
        text: `Força: posse média de ${formatValue(sv("average_possession"))}%. Fragilidade: ${otherName} recupera pouco (${formatValue(ov("recoveries_per_game"))} por jogo). Caminho: alongar posses e cansar a pressão.`,
      });
      if (s("recoveries_per_game") !== null && s("recoveries_per_game") >= 60 && o("pass_accuracy") !== null && o("pass_accuracy") <= 40) consider("press", s("recoveries_per_game") + (100 - o("pass_accuracy")), {
        tag: scoutingTag("Força", self),
        title: `Fragilidade explorável na saída de ${otherName}`,
        text: `Força: ${selfName} recupera ${formatValue(sv("recoveries_per_game"))} bolas por jogo. Fragilidade: ${otherName} troca passes com ${formatValue(ov("pass_accuracy"))}% de precisão. Caminho: pressão alta.`,
      });
      if (s("shots_against_per_game") !== null && s("shots_against_per_game") >= 60 && o("shots_per_game") !== null && o("shots_per_game") >= 60) consider("block_vs_volume", s("shots_against_per_game") + o("shots_per_game"), {
        tag: "Ponto de equilíbrio",
        title: "Volume contra bloqueio",
        text: `Força de ${otherName}: ${formatValue(ov("shots_per_game"))} finalizações por jogo. Força de ${selfName}: só ${formatValue(sv("shots_against_per_game"))} finalizações sofridas por jogo. O duelo passa por quem impõe o ritmo.`,
      });
      if (s("goals_minus_xg") !== null && s("goals_minus_xg") >= 70) consider("efficiency", s("goals_minus_xg"), {
        tag: scoutingTag("Força", self),
        title: `${selfName} converte acima do esperado`,
        text: `Força: ${formatValue(sv("goals_minus_xg"))} gols acima do xG. Ponto de scouting: em jogo truncado, a eficiência pode pesar mais que o volume.`,
        tone: "warning",
      });
    }
    const byKey = new Map();
    for (const candidate of candidates) {
      const current = byKey.get(candidate.key);
      if (!current || candidate.strength > current.strength) byKey.set(candidate.key, candidate);
    }
    const insights = [...byKey.values()].sort((left, right) => right.strength - left.strength).map(candidate => candidate.insight);
    if (insights.length <= 1) {
      const shared = sharedRadarAxes(a, b).sort((left, right) => Math.abs(right.a - right.b) - Math.abs(left.a - left.b));
      const top = shared.filter(item => Math.abs(item.a - item.b) >= 10).slice(0, 3);
      if (top.length) insights.push({
        tag: "Ponto de equilíbrio",
        title: "Diferenças mais relevantes",
        text: `Sem uma fragilidade explorável evidente, o confronto tende aos detalhes. Estes são os eixos em que as campanhas mais divergem.`,
        evidence: top.map(item => compareAxisChip(RADAR_LABELS[item.axis] || item.axis, item.a, item.b)),
      });
      else insights.push({
        tag: "Ponto de equilíbrio",
        title: "Campanhas espelhadas",
        text: `${teamName(a.team)} e ${teamName(b.team)} chegam próximos em ataque, defesa e controle. Bola parada, eficiência pontual e episódios individuais tendem a decidir.`,
      });
    }
    return insights.slice(0, 5);
  }

  const COMPARE_TEAM_METRICS = [
    ["played", "Jogos", "", "higher"], ["wins", "Vitórias", "", "higher"], ["goals_per_game", "Gols por jogo", "", "higher"],
    ["xg_per_game", "xG por jogo", "", "higher"], ["shots_per_game", "Finalizações por jogo", "", "higher"], ["conversion", "Conversão", "%", "higher"],
    ["goals_against_per_game", "Gols sofridos por jogo", "", "lower"], ["xga_per_game", "xG cedido por jogo", "", "lower"], ["shots_against_per_game", "Finalizações sofridas por jogo", "", "lower"],
    ["average_possession", "Posse média", "%", "higher"], ["pass_accuracy", "Precisão de passe", "%", "higher"], ["recoveries_per_game", "Recuperações por jogo", "", "higher"],
    ["tackles_per_game", "Desarmes por jogo", "", "higher"], ["xg_difference", "Saldo de xG", "", "higher"], ["goals_minus_xg", "Gols acima do xG", "", "higher"],
  ];
  const COMPARE_OUTFIELD_METRICS = [
    ["minutes_played", "Minutos", " min", "higher"], ["games", "Jogos", "", "higher"], ["goals", "Gols", "", "higher"],
    ["xg", "xG", "", "higher"], ["goals_per_90", "Gols por 90", "", "higher"], ["xg_per_90", "xG por 90", "", "higher"],
    ["shots_per_90", "Finalizações por 90", "", "higher"], ["shot_conversion", "Conversão", "%", "higher"], ["assists", "Assistências", "", "higher"],
    ["xa_per_90", "xA por 90", "", "higher"], ["key_passes_per_90", "Passes para finalização por 90", "", "higher"], ["pass_accuracy", "Precisão de passe", "%", "higher"],
    ["duels_won", "Duelos vencidos", "", "higher"], ["aerial_won", "Duelos aéreos vencidos", "", "higher"], ["defensive_actions_per_90", "Ações defensivas por 90", "", "higher"],
    ["rating", "Rating médio", "", "higher"],
  ];
  const COMPARE_GOALKEEPER_METRICS = [
    ["minutes_played", "Minutos", " min", "higher"], ["games", "Jogos", "", "higher"], ["saves", "Defesas", "", "higher"],
    ["saves_per_90", "Defesas por 90", "", "higher"], ["accurate_passes", "Passes certos", "", "higher"], ["pass_accuracy", "Precisão de passe", "%", "higher"],
    ["long_pass_accuracy", "Precisão de passe longo", "%", "higher"], ["rating", "Rating médio", "", "higher"],
  ];
  const COMPARE_NEUTRAL_METRICS = [
    ["minutes_played", "Minutos", " min", "higher"], ["games", "Jogos", "", "higher"], ["accurate_passes", "Passes certos", "", "higher"],
    ["pass_accuracy", "Precisão de passe", "%", "higher"], ["rating", "Rating médio", "", "higher"],
  ];

  function isGoalkeeperEntity(player) {
    return player?.macroposition === "Goleiro" || positionLabel(player?.position) === "GOL";
  }

  function compareMetricTable(kind, a, b) {
    const rowA = kind === "player" ? a.player || {} : a.team || {};
    const rowB = kind === "player" ? b.player || {} : b.team || {};
    let definitions = COMPARE_TEAM_METRICS, notice = null;
    if (kind === "player") {
      const gkA = isGoalkeeperEntity(rowA), gkB = isGoalkeeperEntity(rowB);
      if (gkA && gkB) definitions = COMPARE_GOALKEEPER_METRICS;
      else if (gkA || gkB) { definitions = COMPARE_NEUTRAL_METRICS; notice = "Goleiro e jogador de linha têm repertórios distintos — a tabela mostra apenas métricas comuns às duas funções."; }
      else definitions = COMPARE_OUTFIELD_METRICS;
    }
    // Grupos temáticos colapsáveis: primeira leitura curta, aprofundamento sob demanda.
    const TABLE_GROUPS = {
      team: [
        ["Ataque", ["goals_per_game", "xg_per_game", "shots_per_game", "conversion"]],
        ["Defesa", ["goals_against_per_game", "xga_per_game", "shots_against_per_game"]],
        ["Controle", ["average_possession", "pass_accuracy", "recoveries_per_game", "tackles_per_game"]],
        ["Eficiência e campanha", ["played", "wins", "xg_difference", "goals_minus_xg"]],
      ],
      player: [
        ["Produção", ["minutes_played", "games", "goals", "xg"]],
        ["Eficiência", ["goals_per_90", "xg_per_90", "shots_per_90", "shot_conversion"]],
        ["Criação", ["assists", "xa_per_90", "key_passes_per_90"]],
        ["Posse e passe", ["accurate_passes", "pass_accuracy", "long_pass_accuracy"]],
        ["Duelos e defesa", ["duels_won", "aerial_won", "defensive_actions_per_90", "saves", "saves_per_90", "rating"]],
      ],
    };
    const buildRow = ([key, labelText, unit, direction]) => {
      const va = number(rowA[key]), vb = number(rowB[key]);
      if (va === null && vb === null) return null;
      const leadA = va !== null && vb !== null && va !== vb && (direction === "lower" ? va < vb : va > vb);
      const leadB = va !== null && vb !== null && va !== vb && !leadA;
      return node("tr", {}, [
        node("td", { class: leadA ? "is-lead-a" : "", text: va === null ? "—" : `${formatValue(va)}${unit}` }),
        node("td", { class: "compare-metric-label", text: labelText }),
        node("td", { class: leadB ? "is-lead-b" : "", text: vb === null ? "—" : `${formatValue(vb)}${unit}` }),
      ]);
    };
    const nameA = kind === "player" ? personName(rowA) : teamName(rowA);
    const nameB = kind === "player" ? personName(rowB) : teamName(rowB);
    const tableHead = () => node("thead", {}, node("tr", {}, [
      node("th", { class: "is-side-a" }, [flagNode({ team_name: rowA.team_name || (kind === "team" ? rawTeamName(rowA) : null) }), node("span", { text: nameA })]),
      node("th", { text: "Métrica" }),
      node("th", { class: "is-side-b" }, [flagNode({ team_name: rowB.team_name || (kind === "team" ? rawTeamName(rowB) : null) }), node("span", { text: nameB })]),
    ]));
    const byKey = new Map(definitions.map(definition => [definition[0], definition]));
    const groups = (TABLE_GROUPS[kind] || [["Métricas", definitions.map(d => d[0])]])
      .map(([title, keys]) => [title, keys.map(key => byKey.get(key)).filter(Boolean).map(buildRow).filter(Boolean)])
      .filter(([, rows]) => rows.length);
    if (!groups.length) return null;
    const playedDiffers = kind === "team" && number(rowA.played) !== null && number(rowB.played) !== null && number(rowA.played) !== number(rowB.played);
    return node("section", { class: "compare-table-section" }, [
      node("header", {}, [node("h3", { text: "Números lado a lado" }), node("p", { text: notice || "O valor destacado indica quem leva a melhor em cada métrica (considerando se mais alto ou mais baixo é melhor)." })]),
      playedDiffers ? node("p", { class: "compare-table-note", text: `Número de jogos diferente (${formatValue(rowA.played)} × ${formatValue(rowB.played)}) — priorize as métricas por jogo; os totais de campanha não são diretamente comparáveis.` }) : null,
      ...groups.map(([title, rows], index) => node("details", { class: "compare-table-group", open: index === 0 ? "" : null }, [
        node("summary", {}, [node("span", { text: title }), node("strong", { text: `${rows.length} métricas` })]),
        node("div", { class: "table-wrap compare-table" }, [node("table", {}, [tableHead(), node("tbody", {}, rows)])]),
      ])),
    ].filter(Boolean));
  }

  function compareRadarFeature(kind, a, b) {
    const shared = sharedRadarAxes(a, b);
    const rowA = kind === "player" ? a.player || {} : a.team || {};
    const rowB = kind === "player" ? b.player || {} : b.team || {};
    const nameA = kind === "player" ? personName(rowA) : teamName(rowA);
    const nameB = kind === "player" ? personName(rowB) : teamName(rowB);
    if (shared.length < 3) {
      return node("section", { class: "compare-radar-section" }, [
        node("header", {}, [node("h3", { text: "Radar do confronto" })]),
        node("p", { class: "profile-empty", text: kind === "player" ? "Goleiro e jogador de linha são avaliados em eixos diferentes — use a tabela e as leituras abaixo." : "Não há eixos suficientes em comum neste recorte." }),
      ]);
    }
    const axesA = shared.map(item => ({ axis: item.axis, value: item.a, available_metrics: item.available_metrics }));
    const axesB = shared.map(item => ({ axis: item.axis, value: item.b }));
    const chart = radarChart(axesA, `${nameA} vs ${nameB}`, axesB, nameB, true);
    const selectedLegend = chart.querySelector?.(".radar-legend .is-selected");
    if (selectedLegend) selectedLegend.textContent = nameA;
    const note = kind === "player"
      ? "Notas 0–100: cada jogador é medido contra a média da própria posição na Copa."
      : "Notas 0–100 em relação às demais seleções da Copa — diretamente comparáveis.";
    return node("section", { class: "compare-radar-section" }, [
      node("header", {}, [node("h3", { text: "Radar do confronto" }), node("p", { text: `${nameA} vs ${nameB}` })]),
      node("div", { class: "compare-radar" }, chart),
      node("p", { class: "profile-radar-note", text: note }),
    ]);
  }

  function compareIdentityStrip(kind, a, b) {
    const sideCard = (payload, side) => {
      if (kind === "player") {
        const player = payload.player || {};
        return node("article", { class: `compare-side is-side-${side}` }, [
          playerPhotoNode(player),
          node("span", {}, [
            node("strong", { text: personName(player) }),
            node("small", { text: `${displayTeamName(player.team_name)} · ${resolvedPlayerPosition(player)}` }),
            node("small", { text: `${formatValue(player.minutes_played)} min · ${formatValue(player.games)} ${number(player.games) === 1 ? "jogo" : "jogos"}` }),
            node("button", { type: "button", class: "action-link compare-profile-cta", text: "Ver perfil", onclick: () => goToProfile("player", player.player_id) }),
          ]),
        ]);
      }
      const team = payload.team || {};
      return node("article", { class: `compare-side is-side-${side}` }, [
        flagNode(team, "flag-large"),
        node("span", {}, [
          node("strong", { text: teamName(team) }),
          node("small", { text: [team.group_name ? `Grupo ${team.group_name}` : "Copa 2026", team.classification_status].filter(Boolean).join(" · ") }),
          node("small", { text: `${formatValue(team.played)} jogos · ${formatValue(team.wins)} vitórias · saldo de xG ${signedStandingValue(team.xg_difference)}` }),
          node("button", { type: "button", class: "action-link compare-profile-cta", text: `Ver perfil de ${teamName(team)}`, onclick: () => goToProfile("team", team.team_id) }),
        ]),
      ]);
    };
    const positionsDiffer = kind === "player"
      && resolvedPlayerPosition(a.player || {}) !== resolvedPlayerPosition(b.player || {});
    return node("div", {}, [
      node("div", { class: "compare-identity" }, [sideCard(a, "a"), node("span", { class: "compare-vs", text: "×", "aria-hidden": "true" }), sideCard(b, "b")]),
      positionsDiffer ? node("p", { class: "compare-position-note", text: "Comparação direta entre funções diferentes — algumas métricas favorecem funções específicas; os percentis de cada um são relativos à própria posição." }) : null,
    ].filter(Boolean));
  }

  function compareResultView(kind, a, b) {
    if (!a?.available || !b?.available) return emptyState("Comparação indisponível", "Não foi possível carregar os dois perfis neste recorte.");
    const insights = kind === "player" ? playerMatchupInsights(a, b) : teamMatchupInsights(a, b);
    const insightsTitle = kind === "player" ? "Onde cada um leva a melhor" : "Scouting do confronto";
    const insightsSubtitle = kind === "player"
      ? "Leitura dos eixos comparativos dos dois jogadores neste recorte da Copa."
      : "Forças, fragilidades exploráveis e pontos de equilíbrio a partir das métricas da campanha.";
    return node("div", { class: "compare-result" }, [
      compareIdentityStrip(kind, a, b),
      compareRadarFeature(kind, a, b),
      insightSection(insightsTitle, insightsSubtitle, insights, "compare-insights"),
      compareMetricTable(kind, a, b),
    ].filter(Boolean));
  }

  function profileCompareSelector(data, initial = null) {
    let kind = initial?.kind === "team" ? "team" : "player";
    const slots = { a: null, b: null };
    const payloads = { a: null, b: null };
    let token = 0;
    const output = node("div", { class: "profile-analysis-host compare-output" });
    const kindTabs = attachTabListKeyNav(node("div", { class: "player-profile-tabs compare-kind-tabs", role: "tablist", "aria-label": "Tipo de comparação" }, [
      ["player", "Jogadores"], ["team", "Seleções"],
    ].map(([key, labelText]) => node("button", { type: "button", role: "tab", "data-kind": key, text: labelText, onclick: () => setKind(key) }))));
    const pickers = { a: buildPicker("a"), b: buildPicker("b") };
    const pickersRow = node("div", { class: "compare-pickers" }, [pickers.a.panel, pickers.b.panel]);
    const swapBar = node("div", { class: "compare-swap-bar", hidden: true }, [
      node("button", { type: "button", class: "action-link", text: "Trocar jogadores/seleções", onclick: () => { pickersRow.hidden = false; swapBar.hidden = true; pickersRow.scrollIntoView({ behavior: "smooth", block: "start" }); } }),
    ]);

    function entityList() {
      if (kind === "team") return [...(data.teams || [])].sort((left, right) => teamName(left).localeCompare(teamName(right), "pt-BR"));
      return [...(data.players || [])].sort((left, right) => (number(right.minutes_played) || 0) - (number(left.minutes_played) || 0));
    }
    function entityId(row) { return kind === "team" ? row.team_id : row.player_id; }
    function entityRow(row) {
      const primary = kind === "team" ? teamName(row) : personName(row);
      const secondary = kind === "team"
        ? `${row.group_name ? `Grupo ${row.group_name}` : "Copa 2026"} · ${row.classification_status || "Em disputa"}`
        : `${displayTeamName(row.team_name)} · ${resolvedPlayerPosition(row)}`;
      return [flagNode(row), node("span", {}, [node("strong", { text: primary }), node("small", { text: secondary })])];
    }
    function buildPicker(slot) {
      const search = node("input", { type: "search", placeholder: kind === "team" ? "Buscar seleção" : "Buscar jogador", autocomplete: "off" });
      const results = node("div", { class: "profile-selector-results compare-picker-results" });
      const selected = node("div", { class: "profile-selected-entity", text: "Escolha abaixo." });
      const title = node("h4", { class: "compare-picker-title", text: "" });
      const panel = node("section", { class: `profile-selector-panel compare-picker is-side-${slot}` }, [
        title,
        node("div", { class: "profile-selector-fields" }, node("label", {}, [node("span", { text: "Buscar" }), search])),
        results,
        node("div", { class: "profile-selection-bar" }, selected),
      ]);
      search.oninput = () => drawResults(slot);
      return { panel, search, results, selected, title };
    }
    function drawResults(slot) {
      const picker = pickers[slot];
      const query = picker.search.value.trim().toLocaleLowerCase("pt-BR");
      const otherId = slots[slot === "a" ? "b" : "a"] ? entityId(slots[slot === "a" ? "b" : "a"]) : null;
      const matches = entityList().filter(row => {
        if (entityId(row) === otherId) return false;
        if (!query) return true;
        const haystack = kind === "team" ? teamName(row) : `${personName(row)} ${displayTeamName(row.team_name)}`;
        return haystack.toLocaleLowerCase("pt-BR").includes(query);
      });
      if (!matches.length) {
        picker.results.replaceChildren(node("p", { class: "profile-selector-empty", text: "Nada encontrado com essa busca." }));
        return;
      }
      const rows = matches.slice(0, 30);
      picker.results.replaceChildren(...rows.map(row => node("button", {
        type: "button",
        class: slots[slot] && entityId(slots[slot]) === entityId(row) ? "is-selected" : "",
        onclick: () => select(slot, row),
      }, entityRow(row))));
      if (matches.length > rows.length) picker.results.append(node("p", { class: "profile-selector-truncated", text: `Mostrando ${rows.length} de ${matches.length} — refine a busca para ver mais.` }));
    }
    function drawSelected(slot) {
      const picker = pickers[slot];
      const row = slots[slot];
      if (!row) { picker.selected.textContent = "Escolha abaixo."; return; }
      picker.selected.replaceChildren(...entityRow(row));
    }
    function drawTitles() {
      const noun = kind === "team" ? "Seleção" : "Jogador";
      pickers.a.title.textContent = `${noun} A`;
      pickers.b.title.textContent = `${noun} B`;
      pickers.a.search.placeholder = kind === "team" ? "Buscar seleção" : "Buscar jogador";
      pickers.b.search.placeholder = pickers.a.search.placeholder;
    }
    function syncUrl() {
      const params = new URLSearchParams({ type: "compare", kind });
      if (slots.a) params.set("a", entityId(slots.a));
      if (slots.b) params.set("b", entityId(slots.b));
      history.replaceState(null, "", `${routePath(state.year, "profile")}?${params}`);
    }
    function drawOutput() {
      if (!slots.a || !slots.b) {
        output.replaceChildren(node("p", { class: "profile-empty", text: kind === "team" ? "Escolha duas seleções para ver o confronto." : "Escolha dois jogadores para ver a comparação." }));
        return;
      }
      if (!payloads.a || !payloads.b) {
        output.replaceChildren(node("p", { class: "profile-loading", text: "Carregando comparação..." }));
        return;
      }
      // Com os dois escolhidos, a comparação assume o palco: o seletor colapsa
      // e um botão compacto permite trocar.
      pickersRow.hidden = true;
      swapBar.hidden = false;
      output.replaceChildren(compareResultView(kind, payloads.a, payloads.b));
    }
    async function load() {
      const current = ++token;
      payloads.a = null; payloads.b = null;
      drawOutput();
      if (!slots.a || !slots.b) return;
      const fetchOne = id => kind === "team"
        ? getJSON(`/editions/${state.year}/teams/${encodeURIComponent(id)}`)
        : getJSON(`/editions/${state.year}/players/${encodeURIComponent(id)}?scope=all`);
      try {
        const [resultA, resultB] = await Promise.all([fetchOne(entityId(slots.a)), fetchOne(entityId(slots.b))]);
        if (current !== token) return;
        payloads.a = resultA; payloads.b = resultB;
        drawOutput();
      } catch (error) {
        if (error?.name !== "AbortError" && current === token) output.replaceChildren(emptyState("Comparação indisponível", "Não foi possível carregar um dos perfis."));
      }
    }
    function select(slot, row) {
      slots[slot] = row;
      drawSelected(slot); drawResults("a"); drawResults("b"); syncUrl(); load();
    }
    function setKind(next) {
      if (next === kind) return;
      kind = next; token += 1;
      slots.a = null; slots.b = null; payloads.a = null; payloads.b = null;
      drawKindTabs(); drawTitles(); drawSelected("a"); drawSelected("b");
      pickers.a.search.value = ""; pickers.b.search.value = "";
      drawResults("a"); drawResults("b"); syncUrl(); drawOutput();
    }
    function drawKindTabs() {
      kindTabs.querySelectorAll("button").forEach(button => { const active = button.dataset.kind === kind; button.classList.toggle("is-active", active); button.setAttribute("aria-selected", String(active)); });
    }
    drawKindTabs(); drawTitles(); drawResults("a"); drawResults("b"); drawOutput();
    if (initial?.a || initial?.b) {
      const list = entityList();
      const findRow = id => list.find(row => entityId(row) === id) || null;
      slots.a = initial.a ? findRow(initial.a) : null;
      slots.b = initial.b && initial.b !== initial.a ? findRow(initial.b) : null;
      drawSelected("a"); drawSelected("b"); drawResults("a"); drawResults("b"); syncUrl();
      if (slots.a && slots.b) load();
    }
    return node("div", { class: "compare-experience" }, [
      node("header", { class: "compare-header" }, [
        node("p", { class: "compare-intro", text: "Coloque dois perfis lado a lado: radar sobreposto, leituras de confronto e números métrica a métrica." }),
        kindTabs,
      ]),
      pickersRow,
      swapBar,
      output,
    ]);
  }

  function teamProfileQuickRead(team, benchmarks) {
    const attack = number(benchmarks?.metrics?.xg_per_game?.percentile);
    const defense = number(benchmarks?.metrics?.xga_per_game?.percentile);
    const qualitative = value => value === null ? null : value >= 75 ? "acima da média" : value >= 45 ? "próximo da média" : "abaixo da média";
    const facts = [];
    if (metricAvailable(team.wins) && metricAvailable(team.played)) facts.push(`${formatValue(team.wins)} vitórias em ${formatValue(team.played)} jogos`);
    if (metricAvailable(team.goals_for)) facts.push(`${formatValue(team.goals_for)} gols`);
    if (metricAvailable(team.xg)) facts.push(`${formatValue(team.xg)} xG criado`);
    const readings = [attack !== null ? `produção ofensiva ${qualitative(attack)}` : null, defense !== null ? `proteção defensiva ${qualitative(defense)}` : null].filter(Boolean);
    if (!facts.length) return null;
    return node("p", { class: "profile-quick-read team-profile-reading", text: `${teamName(team)} registrou ${facts.join(", ")}.${readings.length ? ` No comparativo com a Copa, teve ${readings.join(" e ")}.` : ""}` });
  }

  function teamRadarFeature(team, radar, benchmarkRadar, benchmarkLabel, leaderRadar = []) {
    if (radar.length < 4 || benchmarkRadar.length < 4) return null;
    const title = `${teamName(team)} vs média das seleções da Copa`;
    const leaderLabel = "Líder da Copa";
    return node("section", { class: "profile-radar-feature team-radar-feature" }, [
      node("header", {}, [node("h3", { text: "Perfil comparativo" }), node("p", { text: title })]),
      radarChart(radar, title, benchmarkRadar, benchmarkLabel, true, leaderRadar, leaderLabel),
      node("p", { class: "profile-radar-note", text: `Escala 0–100 calculada pelo mesmo método para a seleção e para a média da Copa${leaderRadar.length ? "; a linha pontilhada mostra o melhor valor observado na Copa em cada eixo" : ""}.` }),
    ]);
  }

  function teamShotExperience(data, metric) {
    const shots = data.shot_map || [];
    const color = teamColor(data.team?.team_name || shots[0]?.team_name);
    return node("div", { class: "profile-shot-experience team-shot-experience" }, [
      profileSummaryLine([metric("shots", "Finalizações"), metric("goals_for", "Gols"), metric("xg", "xG"), metric("conversion", "Conversão", "%")]),
      node("section", { class: "profile-shot-map-section" }, [node("h3", { text: "Mapa de finalizações" }), playerShotMapPanel(shots, { color })]),
      node("div", { class: "player-distribution-grid" }, [playerShotMinuteChart(shots, data.shot_benchmark?.minute_bins), playerShotQualityChart(shots)]),
      node("div", { class: "player-distribution-grid" }, [
        distributionWithBenchmark(shots, data.shot_benchmark?.distributions?.body_part, "body_part", "Parte do corpo"),
        distributionWithBenchmark(shots, data.shot_benchmark?.distributions?.shot_type, "shot_type", "Situação da finalização"),
      ]),
    ]);
  }

  function teamMatchLogTable(matches, benchmarks) {
    const ordered = [...matches].sort((left, right) => String(left.match_date || "9999").localeCompare(String(right.match_date || "9999")));
    const cards = node("div", { class: "team-match-cards" }, ordered.map(match => node("article", { class: "team-match-card" }, [
      node("header", {}, [node("strong", {}, [flagNode(match.opponent), node("span", { text: `vs ${displayTeamName(match.opponent)}` })]), node("b", { text: `${formatValue(match.goals_for)}–${formatValue(match.goals_against)}` })]),
      node("p", { text: `${formatMatchDate(match.match_date).split(",")[0]} · ${homeStageLabel(match)}` }),
      node("dl", {}, [["xG criado", match.xg_for], ["xG cedido", match.xg_against], ["Finalizações", match.shots_for], ["Sofridas", match.shots_against]].filter(([, value]) => metricAvailable(value)).map(([labelText, value]) => node("div", {}, [node("dt", { text: labelText }), node("dd", { text: formatValue(value) })]))),
    ])));
    return node("div", { class: "team-match-log-view" }, [teamMatchProductionChart(ordered, benchmarks), cards]);
  }

  function teamProfileView(data, activeTab = "general") {
    if (!data?.available) return emptyState("Seleção não encontrada", data?.notice || "Não há dados suficientes.");
    const team = data.team || {};
    const benchmarks = data.benchmarks || {}, benchmarkLabel = benchmarks.label || "Média da Copa";
    const metric = (key, labelText, unit = "", compactBenchmark = false) => metricWithComparison(labelText, team[key], { unit, benchmark: benchmarks.metrics?.[key], benchmarkLabel, compactBenchmark, standingUniverse: "das seleções", entityValueLabel: "Valor da seleção", universeDescription: "todas as seleções da Copa", entityGames: number(team.played) });
    const metricGroup = (title, definitions) => {
      const rows = definitions.map(([key, labelText, unit]) => metric(key, labelText, unit, true)).filter(Boolean);
      return rows.length ? node("section", { class: "profile-metric-group" }, [node("header", {}, [node("h4", { text: title }), node("small", { text: "Referência: média das seleções da Copa" })]), node("dl", { class: "profile-comparison-grid" }, rows)]) : null;
    };
    const radar = (data.radar || []).filter(axis => metricAvailable(axis.value));
    const benchmarkRadar = (data.benchmark_radar || []).filter(axis => radar.some(selected => selected.axis === axis.axis));
    const leaderRadar = (data.leader_radar || []).filter(axis => radar.some(selected => selected.axis === axis.axis));
    let content;
    if (activeTab === "match_log") {
      content = teamMatchLogTable(data.matches || [], benchmarks);
    } else if (activeTab === "shots") {
      content = teamShotExperience(data, metric);
    } else {
      content = node("div", { class: "team-profile-general" }, [
        teamProfileQuickRead(team, benchmarks),
        teamDiagnosisSection(data),
        teamRadarFeature(team, radar, benchmarkRadar, benchmarkLabel, leaderRadar),
        node("div", { class: "profile-metric-groups" }, [
          // Mirrors the radar's "Ataque" and "Finalização" axes together — both are covered here
          // so the correspondence stays visible without a near-empty single-metric block.
          metricGroup("Ataque e Finalização", [["goals_per_game", "Gols por jogo", ""], ["xg_per_game", "xG por jogo", ""], ["shots_per_game", "Finalizações por jogo", ""], ["conversion", "Conversão", "%"]]),
          metricGroup("Defesa", [["goals_against", "Gols sofridos", ""], ["goals_against_per_game", "Gols sofridos por jogo", ""], ["xga_per_game", "xG cedido por jogo", ""], ["shots_against_per_game", "Finalizações sofridas por jogo", ""]]),
          metricGroup("Controle", [["average_possession", "Posse média", "%"], ["pass_accuracy", "Precisão de passe", "%"], ["recoveries_per_game", "Recuperações por jogo", ""], ["tackles_per_game", "Desarmes por jogo", ""]]),
          metricGroup("Eficiência", [["goals_minus_xg", "Gols acima do xG", ""], ["xg_difference", "Saldo de xG", ""], ["conversion", "Conversão", "%"]]),
        ].filter(Boolean)),
        profileComparablesBlock(data.comparable_teams, "team", team.team_id),
      ].filter(Boolean));
    }
    return node("article", { class: "team-profile-view" }, [
      node("header", { class: "player-profile-identity team-profile-identity" }, [flagNode(team, "flag-large"), node("span", {}, [node("small", { text: [team.group_name ? `Grupo ${team.group_name}` : "Copa 2026", team.classification_status].filter(Boolean).join(" · ") }), node("h3", { text: teamName(team) }), node("p", { text: `${formatValue(team.played)} jogos · ${formatValue(team.wins)} vitórias · ${formatValue(team.goals_for)} gols · saldo de xG ${signedStandingValue(team.xg_difference)}` })]), node("button", { type: "button", class: "profile-compare-shortcut", text: "Comparar com outra seleção", onclick: () => goToCompare("team", team.team_id) })]),
      profileSummaryLine([metricWithComparison("Jogos", team.played), metric("wins", "Vitórias"), metric("goals_for", "Gols"), metric("xg", "xG"), metric("xga", "xG cedido"), metric("xg_difference", "Saldo de xG")]),
      node("div", { class: "player-profile-content team-profile-content" }, content),
    ]);
  }

  function renderPlayerDetail(data) {
    if (!data.available) {
      els.view.replaceChildren(emptyState("Jogador não encontrado", "Ainda não encontramos esse jogador no recorte atual."));
      return;
    }
    const player = data.player || {};
    const fragment = dashboardShell(personName(player), `${teamName(player)} · ${resolvedPlayerPosition(player)}`, data);
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
      profile: renderProfile,
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

  function renderAbout() {
    const fragment = document.createDocumentFragment();
    fragment.append(pageHead("Créditos", "Sobre", "O que é este projeto, de onde vêm os dados e como interpretá-los."));

    fragment.append(section("Sobre o projeto", null, node("div", {}, [
      node("p", { text: "World Cup Analytics é uma leitura editorial e analítica da Copa do Mundo 2026. O produto reúne estatísticas, visualizações, rankings e perfis de partidas, seleções e jogadores — com o objetivo de explicar o torneio, não apenas exibir números." }),
      node("p", { class: "about-disclaimer", text: "Este projeto não é afiliado, endossado ou mantido pela FIFA. Os nomes de seleções e da competição são usados apenas como referência editorial." }),
    ])));

    fragment.append(section("Dados e fontes", null, node("div", {}, [
      node("p", { text: "As estatísticas, eventos, escalações e demais informações analíticas têm como fonte a TheStatsAPI. Métricas derivadas — como agregações por edição, taxas por 90 minutos e percentis por posição — são cálculos próprios feitos a partir dessa fonte." }),
      node("p", { text: "As cores de camisa por partida seguem os documentos oficiais de designação de uniformes da FIFA, com códigos de cor normalizados para uso em interface." }),
    ])));

    fragment.append(section("Metodologia", null, node("dl", { class: "about-method-list" }, [
      ["xG (gols esperados)", "Qualidade acumulada das finalizações, conforme o modelo da fonte. O xG total de uma equipe é a soma das suas finalizações; cobranças de disputa de pênaltis ficam fora de todos os agregados."],
      ["Saldo de xG", "xG criado menos xG cedido — a medida usada para \"seleção mais dominante\"."],
      ["Conversão", "Percentual de finalizações transformadas em gol."],
      ["Métricas por 90", "Valores normalizados para 90 minutos em campo, evitando o viés de quem jogou mais tempo. Rankings por 90 exigem minutos mínimos."],
      ["Rankings e percentis", "Comparações sempre dentro de um universo explícito — jogadores da mesma posição ou todas as seleções da Copa."],
      ["Impacto na partida", "Nota 0–100 que combina rating, ações decisivas (gols, assistências, defesas) e contexto — incluindo pesos específicos para cobranças e defesas em disputas de pênaltis. É uma leitura editorial, não uma métrica oficial."],
    ].map(([term, description]) => node("div", {}, [node("dt", { text: term }), node("dd", { text: description })])))));

    fragment.append(section("Atualização dos dados", null, node("p", {
      text: "Os dados são atualizados conforme a disponibilidade da fonte. Durante a competição, uma rotina automática verifica partidas encerradas e incorpora novos jogos, com rechecagem após cada rodada.",
    })));

    fragment.append(section("Limitações", null, node("ul", { class: "about-limitations" }, [
      "Dados podem sofrer correções posteriores pela fonte — placares, estatísticas e escalações estão sujeitos a revisão.",
      "Algumas métricas dependem da cobertura da fonte e podem não existir para todas as partidas ou jogadores.",
      "Fotos, grafias de nomes e estatísticas podem apresentar inconsistências pontuais.",
    ].map(text => node("li", { text })))));

    fragment.append(section("Criação e contato", null, node("div", {}, [
      node("p", {}, [
        node("span", { text: "Projeto criado por João Vitor Machado de Mello. Mais trabalhos em " }),
        node("a", { href: "https://jvmello.dev", target: "_blank", rel: "noopener", text: "jvmello.dev" }),
        node("span", { text: "." }),
      ]),
      node("p", {}, [
        node("span", { text: "Contato: " }),
        node("a", { href: "mailto:jmachadodemello@gmail.com", text: "jmachadodemello@gmail.com" }),
      ]),
    ])));

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
    if (route.detailId && (route.page === "players" || route.page === "teams")) {
      const kind = route.page === "players" ? "player" : "team";
      history.replaceState(null, "", `${routePath(route.year, "profile")}?type=${kind}&id=${encodeURIComponent(route.detailId)}`);
      return navigate(refresh);
    }
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
      if (state.page === "about") {
        renderAbout();
        document.title = "Sobre · World Cup Analytics";
        requestAnimationFrame(scrollToInternalAnchor);
        return;
      }
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
