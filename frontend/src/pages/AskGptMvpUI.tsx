import React, { useState, useEffect, useRef, useCallback } from "react";
import { useApiClient } from "../utils/apiClient";
import { useAuthSetup } from "../hooks/useAuthSetup";

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
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
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
      <div className="max-w-6xl mx-auto p-6 flex flex-col" style={{ height: 'calc(100vh - 200px)' }}>
        <div className="border rounded-xl shadow-xl p-6 bg-white flex-1 flex flex-col items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Setting up authentication...</p>
          </div>
        </div>
      </div>
    );
  }

  // Show error state if authentication failed
  if (authError) {
    return (
      <div className="max-w-6xl mx-auto p-6 flex flex-col" style={{ height: 'calc(100vh - 200px)' }}>
        <div className="border rounded-xl shadow-xl p-6 bg-white flex-1 flex flex-col items-center justify-center">
          <div className="text-center">
            <p className="text-red-600 mb-4">Authentication Error: {authError}</p>
            <p className="text-gray-600">Please try refreshing the page.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6 flex flex-col" style={{ height: 'calc(100vh - 200px)' }}>
      <div className="border rounded-xl shadow-xl p-6 bg-white flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-bold text-gray-800">SmartCoach AI Assistant</h1>
          <div className="flex gap-2">
            <button
              onClick={() => setShowConversations(!showConversations)}
              className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors"
            >
              {showConversations ? 'Hide' : 'Show'} Conversations
            </button>
            <button
              onClick={createNewConversation}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
            >
              New Chat
            </button>
          </div>
        </div>

        <div className="flex-1 flex gap-4">
          {/* Conversations Sidebar */}
          {showConversations && (
            <div className="w-80 bg-white rounded-lg shadow-lg p-4">
              <h3 className="text-lg font-semibold mb-4">Conversations</h3>
              <div className="space-y-2">
                {conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className={`p-3 rounded-lg cursor-pointer transition-colors ${
                      currentConversationId === conv.id
                        ? 'bg-blue-100 border border-blue-300'
                        : 'bg-gray-50 hover:bg-gray-100'
                    }`}
                    onClick={() => loadConversation(conv.id)}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <p className="font-medium text-sm truncate">{conv.title}</p>
                        <p className="text-xs text-gray-500">
                          {conv.message_count} messages
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConversation(conv.id);
                        }}
                        className="text-red-500 hover:text-red-700 text-xs"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Chat Interface */}
          <div className="flex-1 bg-white rounded-lg shadow-lg flex flex-col">
            {/* Messages Area */}
            <div className="flex-1 p-6 overflow-y-auto">
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 mt-8">
                  <p className="text-lg">Start a conversation with SmartCoach!</p>
                  <p className="text-sm mt-2">Ask about your training, past runs, or upcoming races.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-3xl p-4 rounded-lg ${
                          msg.role === 'user'
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      </div>
                    </div>
                  ))}
                  {loading && (
                    <div className="flex justify-start">
                      <div className="bg-gray-100 text-gray-800 p-4 rounded-lg">
                        <div className="flex items-center gap-2">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
                          SmartCoach is thinking...
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Input Area */}
            <div className="border-t p-4">
              <div className="flex gap-2">
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask SmartCoach about your training, past runs, or upcoming races..."
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                  rows={2}
                  disabled={loading}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={loading || !message.trim()}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200 flex items-center gap-2"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
