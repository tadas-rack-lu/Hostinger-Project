import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import duckdb

# <editor-fold desc="# --- PAGE SET UP & Light Cleaning --- #">
# Load data
file_path = "DataAnalystTaskdata.csv"
df = pd.read_csv(file_path)

# Clean fields
df['is_auto_renew'] = df['is_auto_renew'].fillna(False).astype(bool)
df['started_at'] = pd.to_datetime(df['started_at'], errors='coerce')
df['ar_valid_to'] = pd.to_datetime(df['ar_valid_to'], errors='coerce')
df['ended_at'] = pd.to_datetime(df['ended_at'], errors='coerce')
df['period_months'] = pd.to_numeric(df['period_months'], errors='coerce')
df['payment_gateway'] = df['payment_gateway'].fillna('unknown')

# Register in DuckDB
duckdb.register('subs', df)

st.set_page_config(page_title="Hostinger Auto-Renew Project", layout="wide")
st.title("Auto-Renew Manual Disable Breakdown")
# </editor-fold>

# <editor-fold desc="# --- NOTES & DATA PREVIEW --- #">
st.subheader("Assignment Notes")
st.markdown("""
<div style="background-color: #f0f0f0; padding: 10px; border-radius: 5px;">
    <b>Assumption:</b> The one assumption I had in the data was regarding the <code>is_auto_renew</code>.
    Upon initially reading the instructions, I had assumed that the subscriptions that disabled auto-renew early did not have a <code>True</code> value.
    However, because there is no value of <code>valid_to</code>, it cannot be assumed if their auto-renew was disabled or not.
    Furthermore, there are a substantial amount of subscriptions in which their <code>is_auto_renew</code> value is <code>True</code>,
    and their auto-renew <code>valid_to</code> is earlier than <code>ended_at</code> regarding their subscription.
</div>
""", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)
with st.expander("Data Preview"): st.dataframe(df, hide_index=True)
# </editor-fold>
st.divider()

# <editor-fold desc="# --- BAR CHARTS --- #">
st.subheader("Basic Facts")

# --- Bar Chart 1: Auto-Renew ON vs OFF ---
status_df = duckdb.sql("""
    SELECT 
        CASE WHEN is_auto_renew THEN 'Auto-Renew ON' ELSE 'Auto-Renew OFF' END AS status,
        COUNT(*) AS count
    FROM subs
    GROUP BY 1
""").df()

fig1 = go.Figure([go.Bar(
    x=status_df['status'],
    y=status_df['count'],
    marker_color=['#6EA6DF', '#FE7676']
)])
fig1.update_layout(title="Auto-Renew Status (ON vs OFF)", font=dict(family="sans-serif"))

# --- Bar Chart 2: 12m vs 1m among Auto-Renew ON ---
duration_on_df = duckdb.sql("""
    SELECT 
        CASE WHEN period_months = 12 THEN '12-Month' ELSE '1-Month' END AS duration,
        COUNT(*) AS count
    FROM subs
    WHERE is_auto_renew = TRUE AND period_months IN (1, 12)
    GROUP BY 1
    ORDER BY duration DESC
""").df()

fig2 = go.Figure([go.Bar(
    x=duration_on_df['duration'],
    y=duration_on_df['count'],
    marker_color=['#6EA6DF', '#A8C8EB']
)])
fig2.update_layout(title="Duration Breakdown (Among Auto-Renew ON)", font=dict(family="sans-serif"))

# --- Bar Chart 3: Disabled Early vs Active Until End (Among Auto-Renew ON) ---
disabled_status_df = duckdb.sql("""
    SELECT 
        CASE 
            WHEN ar_valid_to < ended_at THEN 'Disabled Early'
            ELSE 'Active Until End'
        END AS status,
        COUNT(*) AS count
    FROM subs
    WHERE is_auto_renew = TRUE AND ar_valid_to IS NOT NULL AND ended_at IS NOT NULL
    GROUP BY 1
""").df()

fig3 = go.Figure([go.Bar(
    x=disabled_status_df['status'],
    y=disabled_status_df['count'],
    marker_color=['#FE7676', '#6EA6DF']
)])
fig3.update_layout(title="Auto-Renew ON: Disabled Early vs Active Until End", font=dict(family="sans-serif"))

# --- Bar Chart 4: 12m vs 1m among Disabled Early (subset of Auto-Renew ON) ---
duration_disabled_df = duckdb.sql("""
    SELECT 
        CASE WHEN period_months = 12 THEN '12-Month' ELSE '1-Month' END AS duration,
        COUNT(*) AS count
    FROM subs
    WHERE is_auto_renew = TRUE
      AND ar_valid_to IS NOT NULL
      AND ended_at IS NOT NULL
      AND ar_valid_to < ended_at
      AND period_months IN (1, 12)
    GROUP BY 1
    ORDER BY duration DESC
""").df()

fig4 = go.Figure([go.Bar(
    x=duration_disabled_df['duration'],
    y=duration_disabled_df['count'],
    marker_color=['#FE7676', '#ffa0a0']
)])
fig4.update_layout(title="Duration Breakdown (Among Disabled Early)", font=dict(family="sans-serif"))

# --- Display Charts ---
barchr1, barchr2, barchr3, barchr4 = st.columns(4)
with barchr1:
    st.plotly_chart(fig1, use_container_width=True)
with barchr2:
    st.plotly_chart(fig2, use_container_width=True)
with barchr3:
    st.plotly_chart(fig3, use_container_width=True)
with barchr4:
    st.plotly_chart(fig4, use_container_width=True)
# </editor-fold>
st.divider()

# <editor-fold desc="# --- WHEN --- #">
st.subheader("When Are Users Disabling Auto Renew?")
# --- DuckDB Query for 12-Month Subscriptions (Cancel Month) ---
cancel_month_df = duckdb.sql("""
    SELECT 
        LEAST(FLOOR(DATE_DIFF('day', started_at, ar_valid_to) / 30) + 1, 12) AS cancel_month,
        COUNT(*) AS count
    FROM subs
    WHERE is_auto_renew = TRUE
      AND ar_valid_to IS NOT NULL
      AND ended_at IS NOT NULL
      AND ar_valid_to < ended_at
      AND period_months = 12
    GROUP BY cancel_month
    ORDER BY cancel_month
""").df()

# Create bar chart
fig_12m = go.Figure()
fig_12m.add_trace(go.Bar(
    x=cancel_month_df['cancel_month'],
    y=cancel_month_df['count'],
    marker_color='#6EA6DF'
))

fig_12m.update_layout(
    title='Auto-Renew Disabled by Month (12-Month Subscriptions)',
    xaxis_title='Month of Subscription',
    yaxis_title='Number of Disables',
    font=dict(family='sans-serif'),
    xaxis=dict(
        tickmode='linear',
        tick0=1,
        dtick=1,
        range=[0.5, 12.5]
    )
)


# --- DuckDB Query for 1-Month Subscriptions (Cancel Day) ---
cancel_day_df = duckdb.sql("""
    SELECT 
        DATE_DIFF('day', started_at, ar_valid_to) AS cancel_day,
        COUNT(*) AS count
    FROM subs
    WHERE is_auto_renew = TRUE
      AND ar_valid_to IS NOT NULL
      AND ended_at IS NOT NULL
      AND ar_valid_to < ended_at
      AND period_months = 1
    GROUP BY cancel_day
    ORDER BY cancel_day
""").df()

# Create bar chart
fig_1m = go.Figure()
fig_1m.add_trace(go.Bar(
    x=cancel_day_df['cancel_day'],
    y=cancel_day_df['count'],
    marker_color='#FE7676'
))

fig_1m.update_layout(
    title='Auto-Renew Disabled by Day (1-Month Subscriptions)',
    xaxis_title='Day of Subscription',
    yaxis_title='Number of Disables',
    font=dict(family='sans-serif'),
    xaxis=dict(
        tickmode='linear',
        tick0=0,
        dtick=1,
        range=[-0.5, cancel_day_df['cancel_day'].max() + 0.5]
    )
)


# --- Display Charts
col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(fig_12m, use_container_width=True)
with col2:
    st.plotly_chart(fig_1m, use_container_width=True)
st.markdown("""
<div style="background-color: #f0f0f0; padding: 10px; border-radius: 5px;">
    <b>Takeaway:</b><br>
    For <b>1-month subscriptions</b>, there’s no strong pattern in when users disable auto-renew, aside from a noticeable spike on <b>Day 1</b>.<br><br>
    In contrast, <b>12-month subscriptions</b> show two key peaks:
    <ul>
        <li>A small increase on the <b>first day</b></li>
        <li>A dramatic spike during the <b>final month</b>, particularly on the <b>very last day</b> of the subscription</li>
        <li>Months have a relatively stable amount of users disabling, with a small peak in October & November 
    </ul>
</div>
""", unsafe_allow_html=True)

# --- FIRST 7 DAYS ---
first_week_df = duckdb.sql("""
    SELECT 
        DATE_DIFF('day', started_at, ar_valid_to) AS days_after_start,
        COUNT(*) AS count
    FROM subs
    WHERE period_months = 12
      AND is_auto_renew = TRUE
      AND ar_valid_to IS NOT NULL
      AND ended_at IS NOT NULL
      AND ar_valid_to < ended_at
      AND DATE_DIFF('day', started_at, ar_valid_to) BETWEEN 0 AND 6
    GROUP BY days_after_start
    ORDER BY days_after_start
""").df()

first_counts = {i: 0 for i in range(7)}
first_counts.update(first_week_df.set_index('days_after_start')['count'].to_dict())

# --- LAST 7 DAYS ---
last_week_df = duckdb.sql("""
    SELECT 
        DATE_DIFF('day', ar_valid_to, ended_at) AS days_before_end,
        COUNT(*) AS count
    FROM subs
    WHERE period_months = 12
      AND is_auto_renew = TRUE
      AND ar_valid_to IS NOT NULL
      AND ended_at IS NOT NULL
      AND ar_valid_to < ended_at
      AND DATE_DIFF('day', ar_valid_to, ended_at) BETWEEN 1 AND 7
    GROUP BY days_before_end
    ORDER BY days_before_end
""").df()

last_counts = {i: 0 for i in range(1, 8)}
last_counts.update(last_week_df.set_index('days_before_end')['count'].to_dict())

# --- SHARED MAX Y ---
max_y = max(max(first_counts.values()), max(last_counts.values()))

# --- FIGURE 1: First 7 Days ---
fig_first = go.Figure()
fig_first.add_trace(go.Bar(
    x=list(range(7)),
    y=[first_counts[i] for i in range(7)],
    marker_color='#6EA6DF'
))
fig_first.update_layout(
    title='Auto-Renew Disables in First 7 Days (12-Month Subscriptions)',
    xaxis_title='Day After Start',
    yaxis_title='Number of Disables',
    font=dict(family='sans-serif'),
    xaxis=dict(
        tickmode='array',
        tickvals=list(range(7)),
        ticktext=[f'Day {i+1}' for i in range(7)],
        range=[-0.5, 6.5]
    ),
    yaxis=dict(range=[0, max_y])
)

# --- FIGURE 2: Last 7 Days (Reversed) ---
x_days = list(range(1, 8))
x_days_reversed = list(reversed(x_days))
y_counts_reversed = [last_counts[i] for i in x_days_reversed]

fig_last = go.Figure()
fig_last.add_trace(go.Bar(
    x=[f'Day {d}' for d in x_days_reversed],  # Day 7 to Day 1
    y=y_counts_reversed,
    marker_color='#FE7676'
))
fig_last.update_layout(
    title='Auto-Renew Disables in Last 7 Days (12-Month Subscriptions)',
    xaxis_title='Days Before End',
    yaxis_title='Number of Disables',
    font=dict(family='sans-serif'),
    xaxis=dict(
        tickmode='linear',
        dtick=1,
        range=[-0.5, 6.5]
    ),
    yaxis=dict(range=[0, max_y])
)

# --- DISABLE MONTHS USING ar_valid_to (Preferred Method) ---
disable_month_df = duckdb.sql("""
    SELECT 
        STRFTIME(ar_valid_to, '%m')::INTEGER AS month_num,
        STRFTIME(ar_valid_to, '%B') AS month_name,
        COUNT(*) AS count
    FROM subs
    WHERE period_months = 12
      AND is_auto_renew = TRUE
      AND ar_valid_to IS NOT NULL
      AND ended_at IS NOT NULL
      AND ar_valid_to < ended_at
    GROUP BY month_num, month_name
    ORDER BY month_num
""").df()

# Create bar chart with Plotly Express
import plotly.express as px

fig_monthly = px.bar(
    disable_month_df,
    x='month_name',
    y='count',
    title='Auto-Renew Disables by Month (12-Month Subs)',
    labels={'count': 'Number of Disables', 'month_name': 'Month'},
    color_discrete_sequence=['teal']
)

fig_monthly.update_traces(textposition='outside')
fig_monthly.update_layout(
    font=dict(family='sans-serif'),
    xaxis_title='Month',
    yaxis_title='Number of Disables',
    xaxis_tickangle=-45
)

# --- DISPLAY WITH OTHERS IN A 3-COLUMN LAYOUT ---
col1, col2, col3 = st.columns(3)
with col1:
    st.plotly_chart(fig_first, use_container_width=True)
with col2:
    st.plotly_chart(fig_last, use_container_width=True)
with col3:
    st.plotly_chart(fig_monthly, use_container_width=True)
# </editor-fold>
st.divider()

# <editor-fold desc="# --- WHO --- #">
st.subheader("Subgroups & Payment Gateway Correlation to Early Disabling of Auto Renew")

# Filtered DataFrames
base_filter = (
    (df['period_months'] == 12) &
    (df['is_auto_renew'] == True)
)

early_disable_filter = (
    base_filter &
    (df['ar_valid_to'].notna()) &
    (df['ended_at'].notna()) &
    (df['ar_valid_to'] < df['ended_at'])
)

total_df = df[base_filter]
early_df = df[early_disable_filter]

# Function to create summary table
def create_summary(group_col):
    total_group = total_df[group_col].value_counts().rename('Total Count')
    early_group = early_df[group_col].value_counts().rename('Early Disable Count')
    combined = pd.concat([total_group, early_group], axis=1).fillna(0)
    combined['Total Count'] = combined['Total Count'].astype(int)
    combined['Early Disable Count'] = combined['Early Disable Count'].astype(int)
    combined['% of Total'] = (combined['Total Count'] / combined['Total Count'].sum() * 100).round(2)
    combined['% of Early Disables'] = (combined['Early Disable Count'] / combined['Early Disable Count'].sum() * 100).round(2)
    return combined.reset_index().rename(columns={'index': group_col})

# Generate summaries
product_sub_group_summary = create_summary('product_sub_group').head(5)
payment_gateway_summary = create_summary('payment_gateway')
payment_gateway_summary = payment_gateway_summary[payment_gateway_summary['Total Count'] >= 100]


# Display in columns
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Top Product Sub Groups")
    st.dataframe(product_sub_group_summary, hide_index=True)

with col2:
    st.markdown("#### Top Payment Gateways")
    st.dataframe(payment_gateway_summary, hide_index=True)

st.markdown("""
<div style="background-color: #f0f0f0; padding: 12px; border-radius: 6px;">
    <b>Takeaway:</b><br><br>
    No single group stands out dramatically in early auto-renew disables:
    <ul style="margin-top: 0.5em;">
        <li><b>Product Subgroups:</b> <code>domain</code> and <code>hosting_shared</code> each make up approximately 50% of the 12-month subscriptions.</li>
        <li><b>Payment Gateways:</b> While <code>checkout</code> is the most commonly used, most gateways show similar early-disable behavior — with roughly half of users disabling early across the board.</li>
    </ul>
</div>
""", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# --- BILLING VS AUTO-RENEW DISABLES --- #
st.subheader("Correlation between Billing Amount & Auto-Renew Disable Rates")

# Prepare data
df_filtered = df[
    (df['period_months'] == 12) &
    (df['is_auto_renew'] == True) &
    (df['ar_valid_to'].notna()) &
    (df['ended_at'].notna()) &
    (df['billings_eur_excl_vat'].notna())
].copy()

df_filtered['days_before_renewal'] = (df_filtered['ar_valid_to'] - df_filtered['ended_at']).dt.days
early_disables = df_filtered[df_filtered['days_before_renewal'] >= 0].copy()
early_disables['billing_bin'] = early_disables['billings_eur_excl_vat'].round(0)

# Count disables by billing amount
billing_counts = early_disables['billing_bin'].value_counts().sort_index()

# Full range chart
fig_all = go.Figure()
fig_all.add_trace(go.Scatter(
    x=billing_counts.index,
    y=billing_counts.values,
    mode='lines+markers',
    line=dict(color='darkgreen'),
    name='All Prices'
))
fig_all.update_layout(
    title='Auto-Renew Disables vs Billing Amount (All)',
    xaxis_title='Billing Amount (EUR, excl. VAT)',
    yaxis_title='Number of Disables',
    font=dict(family='sans-serif')
)

# Zoomed (0–8 EUR)
billing_zoom = billing_counts[(billing_counts.index >= 0) & (billing_counts.index <= 8)]
fig_zoom = go.Figure()
fig_zoom.add_trace(go.Scatter(
    x=billing_zoom.index,
    y=billing_zoom.values,
    mode='lines+markers',
    line=dict(color='darkgreen'),
    name='€0–€8 Focus'
))
fig_zoom.update_layout(
    title='Auto-Renew Disables by Billing Amount (€0–€8)',
    xaxis_title='Billing Amount (EUR, excl. VAT)',
    yaxis_title='Number of Disables',
    font=dict(family='sans-serif')
)

# Show side-by-side
col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(fig_all, use_container_width=True)
with col2:
    st.plotly_chart(fig_zoom, use_container_width=True)

st.markdown("""
<div style="background-color: #f0f0f0; padding: 12px; border-radius: 6px;">
    <b>Takeaway:</b><br>
    While there is much higher activity in the €0–€8 range, this is also where most data points lie within the dataframe
</div>
""", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)
# </editor-fold">
st.divider()

# --- INSIGHTS & SUGGESTIONS --- #
st.markdown("""
<div style='background-color: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 6px solid #FE7676; font-family: sans-serif;'>
    <h4>Key Insights</h4>
    <ol style='margin-left: 1em;'>
        <li><b>Widespread Use of Auto-Renew</b><br>
            Roughly <b>75%</b> of all subscriptions had auto-renew enabled at some point.
            Among these, over <b>90%</b> were <code>12-month</code> subscriptions.
        </li>
        <li><b>High Rate of Manual Cancellations</b><br>
            More than <b>50%</b> of users with auto-renew enabled disabled it before their subscription ended.
            Over <b>95%</b> of these early disables were from <code>12-month</code> subscriptions.
        </li>
        <li><b>Timing of Cancellations</b><br>
            <ul>
                <li><code>1-month</code> subscriptions show no consistent pattern, aside from a spike on <b>Day 1</b>.</li>
                <li><code>12-month</code> subscriptions show a small bump on <b>Day 1</b> and a dramatic spike on the <b>last day</b>.</li>
                <li>Subtle seasonal increases appear in <b>October</b> and <b>November</b>.</li>
            </ul>
        </li>
        <li><b>Start & End Behavior</b><br>
            The <b>first day</b> and the <b>very last day</b> of a <code>12-month</code> subscription are the top two moments when users disable auto-renew.
        </li>
        <li><b>No Strong Skew by Product or Payment</b><br>
            No <code>product subgroup</code> or <code>payment gateway</code> showed a disproportionate rate of early disables — most hover near 50%.
        </li>
        <li><b>Billing Amount Doesn’t Dictate Behavior</b><br>
            Most disables occurred in the <code>€0–€8</code> range, but this aligns with overall pricing patterns, not necessarily pricing sensitivity.
        </li>
    </ol>
</div>
""", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style='background-color: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 6px solid #6EA6DF; font-family: sans-serif;'>
    <h4>💡 Suggestions to Improve Auto-Renew Rate</h4>
    <ol style='margin-left: 1em;'>
        <li><b>Introduce “Renewal Reminder” Campaign</b><br>
            <i>Timing:</i> Trigger an email 10–14 days before subscription ends.<br>
            <i>Content:</i> Highlight benefits of staying, upcoming price changes, or loyalty perks.
        </li>
        <li><b>Post-Purchase Onboarding Reminder</b><br>
            Prevent Day 1 disables by:
            <ul>
                <li>Making the auto-renew option more transparent at checkout.</li>
                <li>Sending a friendly explainer email shortly after purchase.</li>
            </ul>
        </li>
        <li><b>Offer Renewal Incentives</b><br>
            Especially for the <code>€0–€8</code> group, offer:
            <ul>
                <li>Early bird discounts</li>
                <li>Small loyalty bonuses for keeping auto-renew on</li>
            </ul>
        </li>
        <li><b>In-App Nudge / Pop-Up</b><br>
            For users visiting the dashboard near renewal:<br>
            <i>“Your plan will renew in X days. Enjoy uninterrupted service or explore alternatives now.”</i>
        </li>
    </ol>
</div>
""", unsafe_allow_html=True)
