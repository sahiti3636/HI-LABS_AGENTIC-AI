"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { LiquidButton } from "@/components/ui/liquid-glass-button"
import { Mockup } from "@/components/ui/mockup"
import { Glow } from "@/components/ui/glow"
import { Icons } from "@/components/ui/icons"

export const HeroSection = () => {
    return (
        <section className="relative overflow-hidden px-6 py-24 md:py-32">
            <Glow variant="top" className="opacity-50" />
            <div className="container relative mx-auto flex flex-col items-center text-center">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                >
                    <Badge variant="secondary" className="mb-4 bg-brand/10 text-brand border-brand/20 px-4 py-1">
                        <Icons.brain className="mr-2 h-4 w-4" />
                        Autonomous Roster Agent
                    </Badge>
                </motion.div>

                <motion.h1
                    className="max-w-4xl text-5xl font-extrabold tracking-tight md:text-7xl"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                >
                    Intelligence for your <span className="text-brand">Healthcare Roster</span> Pipelines
                </motion.h1>

                <motion.p
                    className="mt-6 max-w-2xl text-lg text-muted-foreground"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                >
                    Automate ingestion, mapping, and validation with RosterIQ. Deploy diagnostic agents
                    that fix anomalies before they reach your DART reports.
                </motion.p>

                <motion.div
                    className="mt-10 flex flex-wrap gap-4"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.3 }}
                >
                    <LiquidButton className="px-10 h-14 text-lg font-bold">
                        Launch Agent Console
                    </LiquidButton>
                    <LiquidButton className="px-10 h-14 text-lg font-bold">
                        View Analytics
                    </LiquidButton>
                </motion.div>

                <motion.div
                    className="mt-20 w-full max-w-5xl"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.8, delay: 0.4 }}
                >
                    <Mockup className="border-border bg-card/50 backdrop-blur-2xl shadow-2xl shadow-brand/10">
                        <div className="flex h-full items-start justify-center bg-gradient-to-br from-[#a7c2e2]/20 to-brand/5 p-8">
                            <div className="w-full h-full bg-white/40 rounded-2xl border border-white/60 p-6 backdrop-blur-sm overflow-hidden shadow-inner">
                                <div className="flex items-center justify-between mb-8">
                                    <div className="flex items-center gap-3">
                                        <div className="h-3 w-3 rounded-full bg-red-400" />
                                        <div className="h-3 w-3 rounded-full bg-yellow-400" />
                                        <div className="h-3 w-3 rounded-full bg-green-400" />
                                    </div>
                                    <div className="flex gap-2">
                                        <div className="h-6 w-24 bg-brand/20 rounded-full" />
                                        <div className="h-6 w-16 bg-muted/20 rounded-full" />
                                    </div>
                                </div>
                                <div className="grid grid-cols-4 gap-4 mb-8">
                                    {[1, 2, 3, 4].map(i => (
                                        <div key={i} className="bg-white/60 p-4 rounded-xl border border-white/80 shadow-sm transition-all hover:scale-[1.02]">
                                            <div className="h-3 w-1/2 bg-muted/30 rounded mb-2" />
                                            <div className="h-6 w-3/4 bg-brand/30 rounded" />
                                        </div>
                                    ))}
                                </div>
                                <div className="grid grid-cols-3 gap-6">
                                    <div className="col-span-2 bg-white/60 p-6 rounded-xl border border-white/80 h-64 relative overflow-hidden shadow-sm">
                                        <div className="flex gap-2 mb-4">
                                            <div className="h-4 w-32 bg-muted/40 rounded" />
                                        </div>
                                        <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-brand/10 to-transparent flex items-end p-4">
                                            <div className="flex items-end gap-1 w-full h-full">
                                                {[40, 70, 45, 90, 65, 80, 50, 85, 95, 60, 75].map((h, i) => (
                                                    <div key={i} className="flex-1 bg-brand/40 rounded-t-sm" style={{ height: `${h}%` }} />
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="space-y-4">
                                        {[1, 2, 3].map(i => (
                                            <div key={i} className="bg-white/60 p-4 rounded-xl border border-white/80 flex items-center gap-3 shadow-sm">
                                                <div className="h-10 w-10 rounded-full bg-brand/20" />
                                                <div className="flex-1">
                                                    <div className="h-2 w-full bg-muted/30 rounded mb-1" />
                                                    <div className="h-2 w-2/3 bg-muted/20 rounded" />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </Mockup>
                </motion.div>
            </div>
        </section>
    )
}
