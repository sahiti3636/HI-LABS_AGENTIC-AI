"use client"

import React, { useState, useEffect, useRef } from "react"
import { PromptInputBox } from "@/components/ui/ai-prompt-box"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { motion, AnimatePresence } from "framer-motion"
import { Icons } from "@/components/ui/icons"
import { VisualizationRenderer } from "./visualization-renderer"
import { ReportViewer } from "./report-viewer"
import ReactMarkdown from "react-markdown"

interface Message {
    role: "user" | "assistant"
    content: string
    reasoning?: string
    chart_hint?: string
    chart_data?: any[]
    report?: any
    search_metadata?: string
}

export const ChatInterface = () => {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "assistant",
            content: "System initialized. Hello, I'm RosterIQ. I have access to the roster pipeline and market success rates. How can I help you today?"
        }
    ])
    const [isLoading, setIsLoading] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    const scrollToBottom = (instant = false) => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({
                behavior: instant ? "auto" : "smooth",
                block: "end"
            })
        }
    }

    useEffect(() => {
        // Scroll whenever messages change or loading state changes
        const scroll = () => {
            if (messagesEndRef.current) {
                messagesEndRef.current.scrollIntoView({
                    behavior: "smooth",
                    block: "nearest"
                })
            }
        }

        const timer = setTimeout(scroll, 200) // Increase delay for better stability
        return () => clearTimeout(timer)
    }, [messages, isLoading])

    const handleSend = async (query: string, files?: File[]) => {
        const newUserMsg: Message = { role: "user", content: query }
        setMessages(prev => [...prev, newUserMsg])
        setIsLoading(true)

        try {
            const response = await fetch("http://localhost:8000/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    query: query,
                    session_id: "p4-frontend-session"
                }),
            });

            if (!response.ok) {
                throw new Error(`API Error: ${response.statusText}`);
            }

            const data = await response.json();

            const assistantMsg: Message = {
                role: "assistant",
                content: data.answer,
                reasoning: data.reasoning,
                chart_hint: data.chart_hint,
                chart_data: data.chart_data,
                search_metadata: data.sources ? `Sources: ${data.sources.join(", ")}` : undefined
            }
            setMessages(prev => [...prev, assistantMsg])
        } catch (error) {
            console.error("Chat Error:", error);
            const errorMsg: Message = {
                role: "assistant",
                content: `Sorry, I encountered an error connecting to the RosterIQ backend. Please ensure the API is running at http://localhost:8000.`
            }
            setMessages(prev => [...prev, errorMsg])
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="flex flex-col h-full relative overflow-hidden bg-[radial-gradient(125%_125%_at_50%_101%,rgba(245,87,2,1)_10.5%,rgba(245,120,2,1)_16%,rgba(245,140,2,1)_17.5%,rgba(245,170,100,1)_25%,rgba(238,174,202,1)_40%,rgba(202,179,214,1)_65%,rgba(148,201,233,1)_100%)]">
            <ScrollArea className="flex-1 p-6 h-full">
                <div className="max-w-4xl mx-auto space-y-8 pt-12 pb-40">
                    <AnimatePresence>
                        {messages.map((msg, i) => (
                            <motion.div
                                key={i}
                                initial={{ opacity: 0, scale: 0.95, y: 10 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
                            >
                                <Avatar className={`h-8 w-8 shrink-0 ${msg.role === "assistant" ? "bg-white/20 border border-white/30 backdrop-blur-md" : "bg-black/20 border border-black/10 backdrop-blur-md"}`}>
                                    <AvatarFallback className="text-[10px]">
                                        {msg.role === "user" ? <Icons.user className="h-4 w-4" /> : <Icons.brain className="h-4 w-4 text-[#f97316]" />}
                                    </AvatarFallback>
                                </Avatar>

                                <div className={`space-y-3 max-w-[85%] ${msg.role === "user" ? "text-right" : ""}`}>
                                    {msg.reasoning && (
                                        <div className="text-[10px] uppercase tracking-widest text-white/90 bg-black/80 px-2 py-1 rounded-md border border-white/10 backdrop-blur-md inline-block shadow-lg">
                                            Reasoning: {msg.reasoning}
                                        </div>
                                    )}

                                    <div className={`text-sm leading-relaxed p-4 rounded-2xl backdrop-blur-xl ${msg.role === "user" ? "bg-white/90 text-black font-semibold shadow-2xl inline-block text-left" : "bg-black/30 border border-white/10 shadow-2xl text-white prose prose-invert prose-sm"
                                        }`}>
                                        {msg.role === "assistant" ? (
                                            <ReactMarkdown
                                                components={{
                                                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                                                    ul: ({ children }) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
                                                    li: ({ children }) => <li className="mb-1">{children}</li>,
                                                    h3: ({ children }) => <h3 className="text-sm font-bold mt-4 mb-2">{children}</h3>
                                                }}
                                            >
                                                {msg.content}
                                            </ReactMarkdown>
                                        ) : (
                                            msg.content
                                        )}
                                    </div>

                                    {msg.chart_hint && (
                                        <div className="bg-black/40 border border-white/10 rounded-xl p-4 overflow-hidden shadow-2xl backdrop-blur-md">
                                            <VisualizationRenderer type={msg.chart_hint} data={msg.chart_data} />
                                        </div>
                                    )}

                                    {msg.report && (
                                        <ReportViewer data={msg.report} />
                                    )}

                                    {msg.search_metadata && (
                                        <div className="flex items-center gap-2 text-[9px] text-white/50 px-2">
                                            <Icons.globe className="h-3 w-3" />
                                            {msg.search_metadata}
                                        </div>
                                    )}
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                    <div ref={messagesEndRef} />
                </div>
            </ScrollArea>

            {/* Floating Chat Input Area */}
            <div className="absolute bottom-10 left-0 right-0 px-6 z-30">
                <div className="max-w-2xl mx-auto">
                    <PromptInputBox
                        onSend={(message, files) => {
                            handleSend(message, files);
                        }}
                        isLoading={isLoading}
                        placeholder="Type your message here..."
                    />
                </div>
            </div>
        </div>
    )
}
