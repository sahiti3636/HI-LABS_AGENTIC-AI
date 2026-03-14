"use client"

import React from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Icons } from "@/components/ui/icons"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"

const memories = [
    { id: 1, type: "episode", text: "Found mapping anomaly in IL BlueShield roster last week", date: "2d ago" },
    { id: 2, type: "fact", text: "State of Wisconsin success rates drop 15% on weekends", date: "5d ago" },
    { id: 3, type: "episode", text: "Successfully resolved SPS load block for Org #882", date: "1w ago" },
]

export const SessionMemorySidebar = () => {
    return (
        <Card className="h-full bg-card border-border flex flex-col shadow-sm">
            <CardHeader className="p-4 border-b border-border bg-muted/30">
                <CardTitle className="text-xs font-bold uppercase tracking-[0.2em] flex items-center gap-2">
                    <Icons.history className="h-3.5 w-3.5 text-brand" />
                    Session Memory
                </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 p-0">
                <ScrollArea className="h-full">
                    <div className="p-4 space-y-4">
                        <div className="space-y-2">
                            <div className="text-[10px] text-muted-foreground uppercase font-bold">Current Context</div>
                            <div className="p-2 rounded-lg bg-brand/5 border border-brand/20 text-xs">
                                Analyzing Illinois market transaction success rates...
                            </div>
                        </div>

                        <div className="space-y-3">
                            <div className="text-[10px] text-muted-foreground uppercase font-bold">Recalled Episodes</div>
                            {memories.map(m => (
                                <div key={m.id} className="group cursor-help">
                                    <div className="text-xs font-medium group-hover:text-brand transition-colors line-clamp-2 italic text-muted-foreground">
                                        "{m.text}"
                                    </div>
                                    <div className="flex items-center justify-between mt-1">
                                        <Badge variant="outline" className="text-[8px] py-0 px-1 border-white/10 uppercase">
                                            {m.type}
                                        </Badge>
                                        <span className="text-[9px] text-muted-foreground">{m.date}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </ScrollArea>
            </CardContent>
        </Card>
    )
}
