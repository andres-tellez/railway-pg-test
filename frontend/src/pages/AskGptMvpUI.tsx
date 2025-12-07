import React, { useState, useEffect, useRef, useCallback } from "react";
import { useApiClient } from "../utils/apiClient";
import { useAuthSetup } from "../hooks/useAuthSetup";
import { AuthGuard } from "../components/AuthGuard";
import RichMessage from "../components/RichMessage";
import axios from "axios";

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface RateLimitStatus {
  remaining: number;
  limit: number;
  used: number;
  retryAfter?: number; // seconds until retry is allowed
}

export default function AskGptMvpUI() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showConversations, setShowConversations] = useState(false);
  const [rateLimit, setRateLimit] = useState<RateLimitStatus | null>(null);
  const [rateLimitError, setRateLimitError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const rateLimitTimerRef = useRef<NodeJS.Timeout | null>(null);
  const api = useApiClient();
  const { isReady, userId, error: authError } = useAuthSetup();

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  };

  const loadConversations = useCallback(async () => {
    console.log("🔄 Loading conversations...", { isReady, userId });
    try {
      const response = await api.get("/api/conversations");
      setConversations(response.data.conversations);
      console.log("✅ Conversations loaded successfully");
    } catch (error) {
      console.error("❌ Error loading conversations:", error);
    }
  }, [api]);

  // Load conversations once authentication is ready
  useEffect(() => {
    if (isReady) {
      loadConversations();
    }
  }, [isReady]); // Remove loadConversations from dependencies to prevent infinite loop

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Auto-scroll to bottom when loading state changes
  useEffect(() => {
    if (!loading) {
      scrollToBottom();
    }
  }, [loading]);

  // Rate limit countdown timer
  useEffect(() => {
    if (rateLimit?.retryAfter && rateLimit.retryAfter > 0) {
      // Clear any existing timer
      if (rateLimitTimerRef.current) {
        clearInterval(rateLimitTimerRef.current);
      }

      // Set up countdown
      rateLimitTimerRef.current = setInterval(() => {
        setRateLimit((prev) => {
          if (!prev || !prev.retryAfter) return prev;
          const newRetryAfter = prev.retryAfter - 1;
          if (newRetryAfter <= 0) {
            // Timer expired, clear the error
            if (rateLimitTimerRef.current) {
              clearInterval(rateLimitTimerRef.current);
              rateLimitTimerRef.current = null;
            }
            setRateLimitError(null);
            // Reset to allow new requests (remaining will be updated on next successful request)
            return { ...prev, retryAfter: 0, remaining: prev.limit };
          }
          return { ...prev, retryAfter: newRetryAfter };
        });
      }, 1000);
    }

    return () => {
      if (rateLimitTimerRef.current) {
        clearInterval(rateLimitTimerRef.current);
        rateLimitTimerRef.current = null;
      }
    };
  }, [rateLimit?.retryAfter]);

  const createNewConversation = async () => {
    try {
      const response = await api.post("/api/conversations", {});
      const newConversation = response.data;
      setCurrentConversationId(newConversation.id);
      setMessages([]);
      setShowConversations(false);
      setConversations(prev => [newConversation, ...prev]);
    } catch (error) {
      console.error("Error creating conversation:", error);
    }
  };

  const loadConversation = async (conversationId: string) => {
    try {
      const response = await api.get(`/api/conversations/${conversationId}`);
      const conversation = response.data;
      setCurrentConversationId(conversationId);
      setMessages(conversation.messages);
      setShowConversations(false);
    } catch (error) {
      console.error("Error loading conversation:", error);
    }
  };

  const deleteConversation = async (conversationId: string) => {
    try {
      await api.delete(`/api/conversations/${conversationId}`);
      setConversations(prev => prev.filter(conv => conv.id !== conversationId));
      if (currentConversationId === conversationId) {
        setCurrentConversationId(null);
        setMessages([]);
      }
    } catch (error) {
      console.error("Error deleting conversation:", error);
    }
  };

  const handleSendMessage = async () => {
    if (!message.trim()) return;
    if (rateLimit?.retryAfter && rateLimit.retryAfter > 0) return; // Rate limited

    // Create new conversation if none exists
    if (!currentConversationId) {
      await createNewConversation();
      return; // Will retry after conversation is created
    }

    setLoading(true);
    setRateLimitError(null);
    const userMessage = message.trim();
    const tempUserMessageId = Date.now().toString();

    // Add user message to UI immediately
    const tempUserMessage: Message = {
      id: tempUserMessageId,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, tempUserMessage]);

    try {
      const response = await api.post(`/api/conversations/${currentConversationId}/messages`, {
        message: userMessage
      });

      const data = response.data;

      // Update rate limit status from response
      if (data.rate_limit) {
        setRateLimit({
          remaining: data.rate_limit.remaining,
          limit: data.rate_limit.limit,
          used: data.rate_limit.used,
          retryAfter: 0,
        });
      }

      // Clear input on success
      setMessage("");

      // Add assistant response to UI
      const assistantMessage: Message = {
        id: data.message_id,
        role: 'assistant',
        content: data.response,
        created_at: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);

    } catch (error: unknown) {
      console.error("Error sending message:", error);

      // Check if it's a rate limit error
      if (axios.isAxiosError(error) && error.response?.status === 429) {
        const errorData = error.response.data as any;
        if (errorData?.error_code === "OPENAI_RATE_LIMIT_EXCEEDED") {
          const retryAfter = errorData.details?.retry_after_seconds || 60;
          setRateLimit({
            remaining: 0,
            limit: errorData.details?.limit ? parseInt(errorData.details.limit.match(/\d+/)?.[0] || "10") : 10,
            used: errorData.details?.limit ? parseInt(errorData.details.limit.match(/\d+/)?.[0] || "10") : 10,
            retryAfter: retryAfter,
          });
          setRateLimitError(null); // Clear any previous errors, timer will show message
          // Remove user message from UI (it was added optimistically)
          setMessages(prev => prev.filter(msg => msg.id !== tempUserMessageId));
          // Keep the message in the input field so they can retry after timer expires
          setMessage(userMessage);
          return;
        }
      }

      // For other errors, remove the temporary user message
      setMessages(prev => prev.filter(msg => msg.id !== tempUserMessageId));
      setRateLimitError("❌ Error sending message. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };








  return (
    <AuthGuard>
    <div className="flex flex-col" style={{ height: 'calc(100vh - 200px)' }}>
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-20">
            <p className="text-lg">Ask me about your training!</p>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-4xl px-6 py-4 rounded-2xl ${
                    msg.role === 'user'
                      ? 'bg-blue-500 text-white'
                      : 'bg-white border border-gray-200 shadow-sm'
                  }`}
                >
                  <RichMessage content={msg.content} role={msg.role} />
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-200 shadow-sm px-6 py-4 rounded-2xl">
                  <div className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-gray-400 border-t-transparent"></div>
                    <span className="text-gray-600">SmartCoach is thinking...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t p-4 bg-white">
        {/* Rate Limit Status */}
        {rateLimit && (
          <div className="mb-2">
            {rateLimit.retryAfter && rateLimit.retryAfter > 0 ? (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-red-800 font-medium">
                    ⏱️ Rate limit exceeded. Retry in {rateLimit.retryAfter}s
                  </span>
                </div>
              </div>
            ) : rateLimit.remaining <= 2 && rateLimit.remaining > 0 ? (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-yellow-800">
                    ⚠️ {rateLimit.remaining} of {rateLimit.limit} requests remaining this minute
                  </span>
                </div>
              </div>
            ) : rateLimit.remaining > 0 ? (
              <div className="text-xs text-gray-500 flex items-center justify-end">
                {rateLimit.remaining} of {rateLimit.limit} requests remaining
              </div>
            ) : null}
          </div>
        )}

        {/* Error Message */}
        {rateLimitError && !rateLimit?.retryAfter && (
          <div className="mb-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-800">
            {rateLimitError}
          </div>
        )}

        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={loading || (rateLimit?.retryAfter ? rateLimit.retryAfter > 0 : false)}
          />
          <button
            onClick={handleSendMessage}
            disabled={
              loading ||
              !message.trim() ||
              (rateLimit?.retryAfter ? rateLimit.retryAfter > 0 : false)
            }
            className="bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {rateLimit?.retryAfter && rateLimit.retryAfter > 0
              ? `Wait ${rateLimit.retryAfter}s`
              : "Send"}
          </button>
        </div>
      </div>
    </div>
    </AuthGuard>
  );
}
