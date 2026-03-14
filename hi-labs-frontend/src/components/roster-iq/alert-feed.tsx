"use client"

import React from "react"
import { Icons } from "@/components/ui/icons"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"

const alerts = [
    { id: 1, msg: "Wisconsin Market latency exceeded threshold (1.2s)", time: "12m ago", severity: "high" },
    { id: 2, msg: "New mapping approval required for Org #291", time: "45m ago", severity: "medium" },
    { id: 3, msg: "Monthly transaction summary ready", time: "2h ago", severity: "low" },
]

export const AlertFeed = () => {
    return (
        <div className="flex flex-col h-full bg-muted/10">
            <div className="p-4 border-b border-border flex items-center justify-between bg-muted/20">
                <div className="text-[10px] font-bold uppercase tracking-[0.2em] flex items-center gap-2">
                    <Icons.bell className="h-3.5 w-3.5 text-brand" />
                    Proactive Alerts
                </div>
                <Badge variant="outline" className="text-[8px] bg-red-500/10 text-red-500 border-red-500/20">3 NEW</Badge>
            </div>
            <ScrollArea className="flex-1">
                <div className="p-2 space-y-1">
                    {alerts.map(a => (
                        <div key={a.id} className="p-3 hover:bg-muted/50 transition-colors rounded-lg cursor-pointer group">
                            <div className="flex gap-3">
                                <div className={`mt-1 h-1.5 w-1.5 rounded-full shrink-0 ${a.severity === 'high' ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]' :
                                    a.severity === 'medium' ? 'bg-amber-500' : 'bg-brand'
                                    }`} />
                                <div className="space-y-1">
                                    <div className="text-xs group-hover:text-brand transition-colors">{a.msg}</div>
                                    <div className="text-[9px] text-muted-foreground uppercase">{a.time}</div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </ScrollArea>
        </div>
    )
}
