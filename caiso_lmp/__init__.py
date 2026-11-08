"""CAISO Fifteen-Minute Market LMP pipeline for energyhertz.com.

Pulls nodal LMPs from CAISO OASIS once per hour, checks them, reshapes them into
one JSON file per 15-minute interval, and publishes the latest 24 hours to
Cloudflare R2. See README.md for the full description.
"""
