# Trend-Following-Trading-Algorithm
The following algorithm is a Trend-Following algorithm that was developed for the RMSCxSmith2024 Algorithmic Case Competition. It consistently came top 3 in each heat.

This algorithm uses two simple moving averages (SMAs) following the average prices (bid+ask / 2) for each ticker over specific time windows. One of the SMAs keeps track of the averages within a large window (long_SMA) while the other keeps track within a smaller window (short_SMA), the difference between the long_SMA and short_SMA is used to determine buy and sell orders.

The competition had specific gross and net position limits, going over these causes fines to incur. In order to prevent the algorithm from consistently going over, we implemented strategies to slow down the aquisition of positions as limits were approached.
