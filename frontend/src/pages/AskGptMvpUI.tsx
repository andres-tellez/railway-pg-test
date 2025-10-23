import React, { useState, useEffect, useRef, useCallback } from "react";
import { useApiClient } from "../utils/apiClient";
import { useAuthSetup } from "../hooks/useAuthSetup";
import RichMessage from "../components/RichMessage";

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

export default function AskGptMvpUI() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showConversations, setShowConversations] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
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

    // Create new conversation if none exists
    if (!currentConversationId) {
      await createNewConversation();
      return; // Will retry after conversation is created
    }

    setLoading(true);
    const userMessage = message.trim();
    setMessage("");

    // Add user message to UI immediately
    const tempUserMessage: Message = {
      id: Date.now().toString(),
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

      // Add assistant response to UI
      const assistantMessage: Message = {
        id: data.message_id,
        role: 'assistant',
        content: data.response,
        created_at: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);

    } catch (error) {
      console.error("Error sending message:", error);
      // Remove the temporary user message on error
      setMessages(prev => prev.filter(msg => msg.id !== tempUserMessage.id));
      alert("❌ Error sending message. Please try again.");
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








  // Show loading state while authentication is being set up
  if (!isReady) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  // Show error state if authentication failed
  if (authError) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">Error: {authError}</p>
          <p>Please refresh the page.</p>
        </div>
      </div>
    );
  }

  return (
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
        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <button
            onClick={handleSendMessage}
            disabled={loading || !message.trim()}
            className="bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
