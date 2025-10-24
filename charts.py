import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import io
import data

def close_chart(ticker: str, frequency: str) -> io.BytesIO:
    frequency_mappings = {
        "5 minute": data.get_five_min_data,
        "hourly": data.get_hourly_data,
        "daily": data.get_daily_data
    }
    chart_title_mappings = {
        "5 minute": "5 Minute",
        "hourly": "Hourly",
        "daily": "Daily"
    }

    times, closes, prev_close = frequency_mappings[frequency](ticker)
    times_naive = [t.replace(tzinfo=None) for t in times]

    final_price = closes[-1]
    if final_price > prev_close:
        line_color = "#34F444FF"
        fill_color = "#34F444FF"
    elif final_price < prev_close:
        line_color = "#FF0E0EFF"
        fill_color = "#FF0E0EFF"
    else:
        line_color = "gray"
        fill_color = "gray"

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_facecolor("black")

    ax.plot(range(len(closes)), closes, color=line_color, linewidth=1.8, zorder=2, label="Price")
    ax.set_xticks(range(0, len(times_naive), len(times_naive)//5))
    ax.set_xticklabels([t.strftime("%b %d %I:%M %p") for t in times[::len(times_naive)//5]])
    
    ymin = min(min(closes), prev_close)

    ax.fill_between(range(len(closes)), closes, ymin,
                    color=fill_color, alpha=0.6, zorder=1)

    ax.axhline(prev_close, color="gray", linestyle="--", linewidth=1, alpha=0.9, label="Prev Close")

    fig.autofmt_xdate(rotation=30)

    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.2f}"))

    ax.set_title(f"{ticker} {chart_title_mappings[frequency]} Price Chart", color="white", fontsize=14)
    ax.set_xlabel("Time", color="white")
    ax.set_ylabel("Price (USD)", color="white")
    ax.tick_params(colors="white")
    ax.legend()

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=plt.gcf().get_facecolor())
    buf.seek(0)
    plt.close()
    return buf

# close_chart("AAPL", "daily")
