"use client"

import React from "react"
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    Cell, PieChart, Pie, Legend, AreaChart, Area
} from "recharts"

export const VisualizationRenderer = ({ type, data }: { type: string, data?: any[] }) => {
    if (!data) return <div className="text-xs text-muted-foreground p-4">Empty visualization data...</div>

    if (type === "stacked_bar" || type === "bar_chart") {
        return (
            <div className="h-[250px] w-full mt-4">
                <div className="text-[10px] uppercase font-bold text-white/70 mb-4 tracking-[0.2em]">Transaction Trends</div>
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                        <XAxis dataKey="name" stroke="rgba(255,255,255,0.5)" fontSize={10} axisLine={false} tickLine={false} />
                        <YAxis stroke="rgba(255,255,255,0.5)" fontSize={10} axisLine={false} tickLine={false} />
                        <Tooltip
                            contentStyle={{ backgroundColor: "rgba(0,0,0,0.8)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "12px", fontSize: "10px", color: "#fff" }}
                            itemStyle={{ color: "#f97316" }}
                        />
                        <Bar dataKey="success" fill="#10b981" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="failure" fill="#ef4444" radius={[4, 4, 0, 0]} />
                        {data[0]?.count && <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />}
                    </BarChart>
                </ResponsiveContainer>
            </div>
        )
    }

    if (type === "pie_chart") {
        const COLORS = ['#f97316', '#3b82f6', '#10b981', '#ef4444', '#8b5cf6', '#ec4899'];
        return (
            <div className="h-[250px] w-full mt-4">
                <div className="text-[10px] uppercase font-bold text-white/70 mb-4 tracking-[0.2em]">Distribution Breakdown</div>
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie
                            data={data}
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={80}
                            paddingAngle={5}
                            dataKey={data[0]?.value ? "value" : Object.keys(data[0]).find(k => typeof data[0][k] === 'number') || "count"}
                        >
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                        </Pie>
                        <Tooltip
                            contentStyle={{ backgroundColor: "rgba(0,0,0,0.8)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "12px", fontSize: "10px", color: "#fff" }}
                        />
                        <Legend wrapperStyle={{ fontSize: '10px', color: 'rgba(255,255,255,0.7)' }} />
                    </PieChart>
                </ResponsiveContainer>
            </div>
        )
    }

    if (type === "line_chart" || type === "area_chart") {
        return (
            <div className="h-[250px] w-full mt-4">
                <div className="text-[10px] uppercase font-bold text-white/70 mb-4 tracking-[0.2em]">Performance Metric Trends</div>
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data}>
                        <defs>
                            <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#f97316" stopOpacity={0.8} />
                                <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                        <XAxis dataKey="name" stroke="rgba(255,255,255,0.5)" fontSize={10} axisLine={false} tickLine={false} />
                        <YAxis stroke="rgba(255,255,255,0.5)" fontSize={10} axisLine={false} tickLine={false} />
                        <Tooltip
                            contentStyle={{ backgroundColor: "rgba(0,0,0,0.8)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "12px", fontSize: "10px", color: "#fff" }}
                        />
                        <Area type="monotone" dataKey={Object.keys(data[0]).find(k => typeof data[0][k] === 'number' && k !== 'name') || "value"} stroke="#f97316" fillOpacity={1} fill="url(#colorValue)" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        )
    }

    return (
        <div className="flex items-center justify-center p-8 text-xs text-muted-foreground uppercase tracking-widest bg-brand/5 border border-dashed border-brand/20 rounded-lg">
            Unsupported chart type: {type}
        </div>
    )
}
