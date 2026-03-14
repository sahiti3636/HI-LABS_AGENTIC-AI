"use client"

import React from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Icons } from "@/components/ui/icons"
import { Badge } from "@/components/ui/badge"

export const ReportViewer = ({ data }: { data: any }) => {
    return (
        <Card className="bg-card border-border overflow-hidden shadow-xl">
            <div className="bg-brand h-1 w-full" />
            <CardHeader className="p-4 border-b border-border bg-muted/30">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-bold flex items-center gap-2">
                        <Icons.fileText className="h-4 w-4" />
                        Market Success Report: {data.state || "Global"}
                    </CardTitle>
                    <Badge className="bg-brand text-black text-[10px]">VERIFIED</Badge>
                </div>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                    {data.stats && Object.entries(data.stats).map(([k, v]: any) => (
                        <div key={k} className="p-2 rounded bg-muted/50 border border-border text-[10px]">
                            <div className="text-muted-foreground uppercase">{k}</div>
                            <div className="text-lg font-bold">{v}</div>
                        </div>
                    ))}
                </div>
                <div className="text-[11px] text-muted-foreground leading-relaxed border-t border-border pt-4">
                    {data.summary || "Summary generation pending system feedback..."}
                </div>
            </CardContent>
        </Card>
    )
}
