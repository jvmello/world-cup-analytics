"""Manual shirt-number curation.

TheStatsAPI never publishes a jersey number for a handful of players (11 in the 2026
edition), so the edition-wide inference in `TheStatsApiBronzeService._jersey_numbers`
cannot fill them. Entries here are hand-checked against official FIFA squad lists and
win over any inferred value. Keyed by provider player_id; tournament numbers are 1-26.

After editing, rebuild the gold serving so match payloads pick the numbers up.
"""

# 2026 players with no number anywhere in the bronze lineups; numbers hand-checked
# against official squad lists (curated 2026-07-12).
JERSEY_NUMBER_OVERRIDES: dict[str, int] = {
    "pl_7256554": 9,  # Jürgen Locadia (Curaçao, F)
    "pl_64954521": 25,  # Hugo Sochurek (Czechia, M)
    "pl_84676652": 23,  # Josué Duverger (Haiti, G)
    "pl_36173331": 26,  # Woodensky Pierre (Haiti, M)
    "pl_3111024": 7,  # Alireza Jahanbakhsh (Iran, F)
    "pl_96294441": 1,  # Fahad Talib (Iraq, G)
    "pl_64316934": 24,  # Zaid Ismail (Iraq, M)
    "pl_84705367": 9,  # Ali Olwan (Jordan, F)
    "pl_30435221": 15,  # Ibrahim Sadeh / Saadeh (Jordan, M)
    "pl_29180336": 7,  # Mohammed Abu Zrayq / Abu Zraiq (Jordan, F)
    "pl_1747977": 7,  # Otabek Shukurov (Uzbekistan, M)
}
