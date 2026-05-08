# -*- coding: utf-8 -*-
import os
import sys
import pandas as pd
import akshare as ak

def env_float(name, default):
    return float(os.getenv(name, default))

def env_int(name, default):
    return int(os.getenv(name, default))

def main():
    limit = env_int("AUTO_STOCK_LIMIT", 10)
    min_amount = env_float("AUTO_MIN_AMOUNT_YI", 5) * 100000000
    min_pct = env_float("AUTO_MIN_PCT", 1.0)
    max_pct = env_float("AUTO_MAX_PCT", 7.0)
    min_turnover = env_float("AUTO_MIN_TURNOVER", 1.0)
    min_volume_ratio = env_float("AUTO_MIN_VOLUME_RATIO", 1.2)
    prefixes = tuple(x.strip() for x in os.getenv("AUTO_ALLOWED_PREFIX", "60,00,30,68").split(",") if x.strip())

    try:
        df = ak.stock_zh_a_spot_em()
    except Exception as exc:
        print(f"[auto_select] 获取全市场行情失败: {exc}", file=sys.stderr)
        print(os.getenv("STOCK_LIST", "600519"))
        return

    df["代码"] = df["代码"].astype(str).str.extract(r"(\d{6})")[0].str.zfill(6)
    df["名称"] = df["名称"].astype(str)

    for col in ["最新价", "涨跌幅", "成交额", "换手率", "量比", "振幅", "60日涨跌幅"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    mask = (
        df["代码"].str.startswith(prefixes)
        & ~df["名称"].str.contains("ST|退|^N", regex=True, na=False)
        & df["最新价"].between(3, 200)
        & df["涨跌幅"].between(min_pct, max_pct)
        & (df["成交额"] >= min_amount)
        & (df["换手率"] >= min_turnover)
        & (df["量比"] >= min_volume_ratio)
    )

    if "60日涨跌幅" in df.columns:
        mask &= df["60日涨跌幅"].fillna(-999) > -25

    cand = df.loc[mask].copy()
    if cand.empty:
        print("[auto_select] 无候选，回退 STOCK_LIST", file=sys.stderr)
        print(os.getenv("STOCK_LIST", "600519"))
        return

    target_pct = 3.5
    cand["score"] = (
        100 - (cand["涨跌幅"] - target_pct).abs() * 12
        + cand["成交额"].rank(pct=True) * 35
        + cand["换手率"].clip(upper=20).rank(pct=True) * 25
        + cand["量比"].clip(upper=5).rank(pct=True) * 25
        - cand.get("振幅", 0).fillna(0) * 1.5
    )

    cand = cand.sort_values("score", ascending=False).head(limit)
    codes = ",".join(cand["代码"].tolist())

    print(f"[auto_select] 选出: {codes}", file=sys.stderr)
    print(codes)

if __name__ == "__main__":
    main()
