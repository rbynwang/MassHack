"""MassHack: a climate-aware collective of Boston buildings with solar and batteries.

Layers (top to bottom):
  grid          -> asks the collective to soak up surplus or use less
  coordinator   -> pools flexibility offers and assigns tasks across members
  trust         -> enforces each member's limits in code and signs receipts
  agents        -> every member forecasts its load (ML), plans its battery, offers hourly flex + cost
  buildings     -> prosumers (solar + battery, own data) and flex members (small businesses, renters)
"""
__version__ = "0.1.0"
