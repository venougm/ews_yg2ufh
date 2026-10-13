#!/usr/bin/env python3
"""Seed kabupaten & kecamatan se-DIY ke EWS lewat REST API (admin-only).

Mengisi 5 kabupaten/kota DIY + seluruh kecamatan (kapanewon/kemantren) sebagai
DATA AWAL di database -- BUKAN hardcode di kode aplikasi. Sistem tetap generik:
daerah lain tinggal ditambah lewat UI "Tambah Kabupaten/Kecamatan".

Konvensi id:
- kabupaten : huruf kecil tanpa spasi  (sleman, bantul, kulonprogo, gunungkidul, kotayogya)
- kecamatan : <kabupaten>-<nama>        (mis. sleman-depok, bantul-jetis, kotayogya-jetis)
  Prefix kabupaten dipakai agar id unik global (ada nama kecamatan kembar, mis.
  "Jetis" di Bantul DAN Kota Yogyakarta).

Idempoten: menjalankan ulang aman -- entri yang sudah ada akan dilewati.

Cara pakai (login admin diperlukan):
  python3 seed_regions_diy.py --base http://localhost:8001 --admin-user admin --admin-pass 'RAHASIA'
  (--admin-pass JANGAN ditulis di file; beri lewat argumen)
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
import urllib.error
import json
import http.cookiejar

PROVINSI = "diy"

# nama tampilan kabupaten -> id
KABUPATEN = {
    "sleman": "Sleman",
    "bantul": "Bantul",
    "kulonprogo": "Kulon Progo",
    "gunungkidul": "Gunungkidul",
    "kotayogya": "Kota Yogyakarta",
}

KECAMATAN = {
    "sleman": [
        "Berbah", "Cangkringan", "Depok", "Gamping", "Godean", "Kalasan",
        "Minggir", "Mlati", "Moyudan", "Ngaglik", "Ngemplak", "Pakem",
        "Prambanan", "Seyegan", "Sleman", "Tempel", "Turi",
    ],
    "bantul": [
        "Bambanglipuro", "Banguntapan", "Bantul", "Dlingo", "Imogiri", "Jetis",
        "Kasihan", "Kretek", "Pajangan", "Pandak", "Piyungan", "Pleret",
        "Pundong", "Sanden", "Sedayu", "Sewon", "Srandakan",
    ],
    "kulonprogo": [
        "Galur", "Girimulyo", "Kalibawang", "Kokap", "Lendah", "Nanggulan",
        "Panjatan", "Pengasih", "Samigaluh", "Sentolo", "Temon", "Wates",
    ],
    "gunungkidul": [
        "Gedangsari", "Girisubo", "Karangmojo", "Ngawen", "Nglipar", "Paliyan",
        "Panggang", "Patuk", "Playen", "Ponjong", "Purwosari", "Rongkop",
        "Saptosari", "Semanu", "Semin", "Tanjungsari", "Tepus", "Wonosari",
    ],
    "kotayogya": [
        "Danurejan", "Gedongtengen", "Gondokusuman", "Gondomanan", "Jetis",
        "Kotagede", "Kraton", "Mantrijeron", "Mergangsan", "Ngampilan",
        "Pakualaman", "Tegalrejo", "Umbulharjo", "Wirobrajan",
    ],
}


def slug(nama: str) -> str:
    """'Kulon Progo' -> 'kulon-progo' untuk bagian id kecamatan."""
    s = nama.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed kabupaten & kecamatan DIY")
    ap.add_argument("--base", default="http://localhost:8001")
    ap.add_argument("--admin-user", default="admin")
    ap.add_argument("--admin-pass", required=True, help="password admin (jangan taruh di file)")
    args = ap.parse_args()

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def call(method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            args.base + path, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with opener.open(req, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    # login admin
    st, _ = call("POST", "/api/login",
                 {"username": args.admin_user, "password": args.admin_pass})
    if st != 200:
        print(f"GAGAL login admin (HTTP {st}). Cek user/password.", file=sys.stderr)
        return 1
    print("login admin OK")

    added_kab = added_kec = skipped = 0

    for kab_id, kab_nama in KABUPATEN.items():
        st, _ = call("POST", "/api/kabupaten",
                     {"id": kab_id, "nama": kab_nama, "provinsi": PROVINSI})
        if st == 201:
            added_kab += 1
            print(f"+ kabupaten {kab_id} ({kab_nama})")
        else:
            skipped += 1  # kemungkinan sudah ada
            print(f"  kabupaten {kab_id}: HTTP {st} (mungkin sudah ada)")

        for nama in KECAMATAN[kab_id]:
            kec_id = f"{kab_id}-{slug(nama)}"
            st, _ = call("POST", f"/api/kabupaten/{kab_id}/kecamatan",
                         {"id": kec_id, "nama": nama, "kabupaten_id": kab_id})
            if st == 201:
                added_kec += 1
                print(f"    + {kec_id} ({nama})")
            else:
                skipped += 1
                print(f"      {kec_id}: HTTP {st} (mungkin sudah ada)")

    print(f"\nSelesai. kabupaten baru={added_kab}, kecamatan baru={added_kec}, dilewati={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
