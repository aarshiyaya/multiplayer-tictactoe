"""
Elo Rating System
- K-factor: 32
- Initial rating: 1200
- Formula: new_rating = old_rating + K * (actual_score - expected_score)
- Expected score: 1 / (1 + 10^((opponent_rating - player_rating) / 400))
"""


def compute_elo(r_player, r_opponent, score, k=32):
    """
    Compute new Elo rating for one player.
    score: 1.0 = win, 0.5 = draw, 0.0 = loss
    """
    expected = 1 / (1 + 10 ** ((r_opponent - r_player) / 400))
    return round(r_player + k * (score - expected))


def update_elo_both(r1, r2, outcome):
    """
    Update Elo for both players using their pre-match ratings.
    outcome: 'player1_win', 'player2_win', or 'draw'
    Returns (new_r1, new_r2).
    """
    if outcome == "player1_win":
        s1, s2 = 1.0, 0.0
    elif outcome == "player2_win":
        s1, s2 = 0.0, 1.0
    else:
        s1, s2 = 0.5, 0.5

    return compute_elo(r1, r2, s1), compute_elo(r2, r1, s2)