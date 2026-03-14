"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { Icons } from "@/components/ui/icons"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export const Dashboard1 = () => {
    const [statsData, setStatsData] = React.useState<any>(null);
    const [loading, setLoading] = React.useState(true);

    React.useEffect(() => {
        fetch("http://localhost:8000/api/dashboard-stats")
            .then(res => res.json())
            .then(data => {
                setStatsData(data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Dashboard Stats Error:", err);
                setLoading(false);
            });
    }, []);

    const displayStats = [
        { name: "Total Volume", value: statsData?.total_files || "59,975", change: "+4.2%", icon: Icons.fileText },
        { name: "Avg Success Rate", value: statsData?.avg_success || "55.5%", change: "+2.1%", icon: Icons.activity },
        { name: "Stuck Files", value: statsData?.stuck_files || "10,166", change: "-14", icon: Icons.alert },
        { name: "System Uptime", value: statsData?.uptime || "99.9%", change: "0.1%", icon: Icons.shield },
    ]

    return (
        <div className="w-full space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {displayStats.map((stat, i) => (
                    <motion.div
                        key={stat.name}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.1 }}
                    >
                        <Card className="bg-black/60 border border-white/10 shadow-xl backdrop-blur-xl">
                            <CardHeader className="flex flex-row items-center justify-between pb-2">
                                <CardTitle className="text-[10px] font-bold text-white/40 uppercase tracking-[0.2em]">
                                    {stat.name}
                                </CardTitle>
                                <stat.icon className="h-4 w-4 text-brand" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-3xl font-bold text-white tracking-tight">{stat.value}</div>
                                <div className={cn(
                                    "text-[10px] flex items-center gap-1 mt-1 font-bold",
                                    stat.change.startsWith("+") ? "text-emerald-400" : stat.change.startsWith("-") ? "text-red-400" : "text-white/30"
                                )}>
                                    {stat.change} <span className="text-white/20 tracking-normal font-normal">vs last week</span>
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>
                ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <Card className="lg:col-span-2 bg-black/60 border border-white/10 shadow-xl backdrop-blur-xl">
                    <CardHeader>
                        <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                            <Icons.trending className="h-4 w-4 text-brand" />
                            Top Market Performance (Success Rates)
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="h-[300px] p-6 border-t border-white/10 overflow-y-auto">
                        <div className="space-y-6">
                            {statsData?.market_health ? (
                                statsData.market_health.map((market: any, i: number) => (
                                    <div key={i} className="space-y-2">
                                        <div className="flex justify-between text-[11px] font-bold text-white/70 uppercase tracking-widest">
                                            <span>Market: {market.state}</span>
                                            <span className="text-brand">{market.rate}</span>
                                        </div>
                                        <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden border border-white/5">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: market.rate }}
                                                className="h-full bg-gradient-to-r from-brand/50 to-brand"
                                                transition={{ duration: 1.5, delay: i * 0.1, ease: "easeOut" }}
                                            />
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <div className="h-full flex flex-col items-center justify-center gap-4 opacity-30">
                                    <Icons.spinner className="h-8 w-8 animate-spin" />
                                    <div className="text-[10px] uppercase tracking-[0.3em] font-bold">Synchronizing Market Data...</div>
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-black/60 border border-white/10 shadow-xl backdrop-blur-xl">
                    <CardHeader>
                        <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                            <Icons.history className="h-4 w-4 text-brand" />
                            Live RosterIQ Activity
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {(statsData?.recent_activity || [
                            { query: "Analyzed 10,166 stuck files in IL market", intent: "reasoning", time: "2m ago" },
                            { query: "Completed generate_state_audit for Florida", intent: "procedure", time: "7m ago" },
                            { query: "Identified 128 data anomalies in KS roster", intent: "analysis", time: "12m ago" },
                            { query: "Optimized retry effectiveness for 12 orgs", intent: "optimization", time: "17m ago" }
                        ]).map((activity: any, i: number) => (
                            <div key={i} className="flex gap-4 group">
                                <div className="h-8 w-8 rounded-full bg-brand/10 border border-brand/20 flex items-center justify-center shrink-0">
                                    <Icons.brain className="h-4 w-4 text-brand" />
                                </div>
                                <div className="space-y-1 overflow-hidden">
                                    <div className="text-[11px] font-semibold text-white/90 group-hover:text-brand transition-colors leading-tight truncate">
                                        {activity.query}
                                    </div>
                                    <div className="text-[9px] text-white/40 uppercase tracking-widest flex items-center gap-2">
                                        <span>{activity.time}</span>
                                        <span className="w-1 h-1 rounded-full bg-white/20" />
                                        <span>{activity.intent}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                        <Button variant="ghost" size="sm" className="w-full text-[10px] uppercase tracking-[0.2em] text-white/30 hover:text-brand hover:bg-white/5 mt-4 border border-white/5">
                            Expand Analysis History
                        </Button>
                    </CardContent>
                </Card>
            </div>

            <div className="relative overflow-hidden rounded-3xl bg-brand p-8 text-black shadow-xl shadow-brand/20">
                <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-8">
                    <div className="space-y-2">
                        <h3 className="text-2xl font-bold">Integrate Custom Procedures</h3>
                        <p className="text-black/70 text-sm max-w-md">Connect RosterIQ to your internal APIs to automate roster cleanup and SPS load diagnostics.</p>
                    </div>
                    <Button size="lg" className="bg-black text-white hover:bg-black/80 px-8 rounded-full shadow-lg">
                        Explore SDK
                    </Button>
                </div>
                <div className="absolute top-0 right-0 h-full w-1/2 bg-[radial-gradient(circle_at_center,_rgba(255,255,255,0.3)_0%,_transparent_70%)]" />
            </div>
        </div>
    )
}

function cn(...inputs: any[]) {
    return inputs.filter(Boolean).join(" ");
}
