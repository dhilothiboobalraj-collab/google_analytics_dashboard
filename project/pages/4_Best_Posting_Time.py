import plotly.express as px
import streamlit as st

try:
    import utils
except ImportError:
    from project import utils

utils.inject_dashboard_style()
utils.setup_refresh()

utils.render_page_header(
    "Best Posting Time",
    "Find the posting hours that are producing the strongest average engagement in the live dataset.",
)
selection, custom_range = utils.build_date_filter()
start_date, end_date = utils.get_date_range(selection, custom_range)

st.markdown("<div class='dashboard-card small'><div class='dashboard-card-title'>Posting time overview</div><p>Use this chart to identify the hour window that generates the best engagement for your content.</p></div>", unsafe_allow_html=True)

best_df = utils.load_best_posting_time()
if best_df.empty:
    st.warning("Best posting time data is not available yet. Run the data collector to populate analytics.")
    st.stop()

best_df = best_df.sort_values(by="hour")
best_df = best_df.copy()
best_df["Value Belongs To"] = "All Platforms - Average Engagement"
st.markdown("<div class='dashboard-card'><div class='dashboard-card-title'>Hourly engagement distribution</div></div>", unsafe_allow_html=True)
fig = px.bar(
    best_df,
    x="hour_label",
    y="avg_engagement",
    title="Hour vs Average Engagement",
    labels={"hour_label": "Hour", "avg_engagement": "Average Engagement Value", "Value Belongs To": "Value Belongs To"},
    text="avg_engagement",
    color="avg_engagement",
    color_continuous_scale=["#1877F2", "#14B8A6", "#F59E0B", "#E4405F"],
    hover_data={"Value Belongs To": True, "avg_engagement": ":.2f"},
)
fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
fig.update_layout(yaxis_tickformat=".2f", showlegend=False)
st.plotly_chart(utils.chart_layout(fig), use_container_width=True)

best_row = best_df.loc[best_df["avg_engagement"].idxmax()]
best_hour = best_row["hour_label"]
best_value = best_row["avg_engagement"]

st.markdown("")
metric_cards = st.columns(3)
metric_cards[0].metric("Best Posting Hour", best_hour)
metric_cards[1].metric("Peak Engagement", f"{best_value:.2f}")
metric_cards[2].metric("High-Impact Window", "Top performer")
