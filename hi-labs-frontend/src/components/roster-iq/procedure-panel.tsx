"use client"

import React from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Icons } from "@/components/ui/icons"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"

const procedures = [
    { id: "diag-1", name: "Pipeline Latency Audit", desc: "Scan ISF to DART generation lifecycle" },
    { id: "diag-2", name: "Org Success Heatmap", desc: "Compare market rates against baseline" },
    { id: "diag-3", name: "Anonymity Scrub", desc: "Verify PII is removed from metadata" },
]

export const ProcedurePanel = () => {
    return (
        <Card className="h-full bg-card border-border flex flex-col shadow-sm">
            <CardHeader className="p-4 border-b border-border bg-muted/30">
                <CardTitle className="text-xs font-bold uppercase tracking-[0.2em] flex items-center gap-2">
                    <Icons.settings className="h-3.5 w-3.5 text-brand" />
                    Diagnostic Procedures
                </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 p-0">
                <ScrollArea className="h-full">
                    <div className="p-4 space-y-3">
                        {procedures.map(p => (
                            <div key={p.id} className="p-3 rounded-xl border border-border bg-muted/20 hover:bg-muted/40 transition-all group">
                                <div className="flex items-start justify-between gap-2">
                                    <div>
                                        <div className="text-xs font-bold group-hover:text-brand transition-colors">{p.name}</div>
                                        <div className="text-[10px] text-muted-foreground mt-0.5">{p.desc}</div>
                                    </div>
                                    <Button size="icon" variant="ghost" className="h-7 w-7 rounded-full bg-brand/10 text-brand hover:bg-brand/20">
                                        <Icons.play className="h-3 w-3" />
                                    </Button>
                                </div>
                            </div>
                        ))}

                        <div className="pt-4 mt-4 border-t border-border">
                            <Button variant="outline" className="w-full text-[10px] h-8 border-dashed border-border hover:border-brand/50 uppercase tracking-widest bg-transparent">
                                <Icons.plus className="mr-2 h-3 w-3" />
                                Add Custom Task
                            </Button>
                        </div>
                    </div>
                </ScrollArea>
            </CardContent>
        </Card>
    )
}
