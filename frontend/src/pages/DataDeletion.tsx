import React, { useMemo, useState } from "react";
import { useApiClient } from "../utils/apiClient";
import { AuthGuard } from "../components/AuthGuard";
import { useAuth0 } from "@auth0/auth0-react";

type DeletionResult = {
  success: boolean;
  message: string;
  deleted?: Record<string, unknown>;
  user_id?: string;
  timestamp?: string;
};

const adminEmailSet = new Set(
  (import.meta.env.VITE_ADMIN_EMAILS || "")
    .split(",")
    .map((email) => email.trim().toLowerCase())
    .filter(Boolean)
);

const DataDeletion: React.FC = () => {
  const api = useApiClient();
  const { user } = useAuth0();
  const [identifierEmail, setIdentifierEmail] = useState("");
  const [identifierUserId, setIdentifierUserId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [result, setResult] = useState<DeletionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = useMemo(() => {
    const email = user?.email?.toLowerCase();
    return !!(email && adminEmailSet.has(email));
  }, [user]);

  const hasIdentifier = !!identifierEmail.trim() || !!identifierUserId.trim();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!hasIdentifier) {
      setError("Provide a user email or user ID to delete.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const payload: Record<string, string> = {};
      if (identifierEmail.trim()) {
        payload.email = identifierEmail.trim();
      }
      if (identifierUserId.trim()) {
        payload.user_id = identifierUserId.trim();
      }

      const response = await api.delete("/api/admin/users", {
        data: payload,
      });

      setResult(response.data);
      setIdentifierEmail("");
      setIdentifierUserId("");
    } catch (err: any) {
      const message =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        "Failed to delete user.";
      setError(message);
    } finally {
      setIsSubmitting(false);
      setShowConfirm(false);
    }
  };

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-md p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-6">
            Administrative Data Deletion
          </h1>
          <p className="text-sm text-gray-600 mb-8">Last Updated: November 10, 2025</p>

          {!isAdmin ? (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-yellow-900 mb-2">
                Restricted Access
              </h2>
              <p className="text-yellow-800">
                This page is restricted to SmartCoach administrators. If you need your
                data deleted, please contact{" "}
                <a
                  href="mailto:support@smartcoach.app"
                  className="underline font-semibold"
                >
                  support@smartcoach.app
                </a>{" "}
                and we will handle the request promptly.
              </p>
            </div>
          ) : (
            <div className="space-y-8 text-gray-700">
              <section>
                <h2 className="text-2xl font-semibold text-gray-900 mb-3">
                  Deletion Scope
                </h2>
                <p>
                  Deleting a user removes all personalized data stored in SmartCoach,
                  including:
                </p>
                <ul className="list-disc pl-6 mt-2 space-y-2">
                  <li>Identity, profile, and Auth0 linkage records</li>
                  <li>Training plans, workout metadata, and analytics artifacts</li>
                  <li>Strava athlete links and stored tokens</li>
                  <li>All synced activities and coaching conversations</li>
                </ul>
                <p className="mt-3 text-red-600 font-semibold">
                  This action is immediate and irreversible.
                </p>
              </section>

              <section>
                <h2 className="text-2xl font-semibold text-gray-900 mb-4">
                  Delete a User
                </h2>
                <form
                  onSubmit={handleSubmit}
                  className="bg-red-50 border-2 border-red-200 rounded-lg p-6 space-y-4"
                >
                  <p className="text-red-800">
                    Provide either the user's email address or internal user ID. Email
                    lookup is case-insensitive.
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        User Email
                      </label>
                      <input
                        type="email"
                        value={identifierEmail}
                        onChange={(event) => setIdentifierEmail(event.target.value)}
                        placeholder="user@example.com"
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Internal User ID
                      </label>
                      <input
                        type="text"
                        value={identifierUserId}
                        onChange={(event) => setIdentifierUserId(event.target.value)}
                        placeholder="UUID"
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
                      />
                    </div>
                  </div>

                  {!showConfirm ? (
                    <button
                      type="button"
                      disabled={!hasIdentifier}
                      onClick={() => setShowConfirm(true)}
                      className="px-6 py-3 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Continue to Confirmation
                    </button>
                  ) : (
                    <div className="space-y-4">
                      <div className="bg-white border border-red-300 rounded-lg p-4">
                        <p className="font-semibold text-red-900 mb-2">
                          Confirm permanent deletion
                        </p>
                        <p className="text-sm text-red-800">
                          The user and all related data will be removed immediately.
                          This cannot be undone.
                        </p>
                      </div>
                      <div className="flex gap-3">
                        <button
                          type="submit"
                          disabled={isSubmitting}
                          className="px-6 py-3 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isSubmitting ? "Deleting..." : "Yes, delete this user"}
                        </button>
                        <button
                          type="button"
                          disabled={isSubmitting}
                          onClick={() => setShowConfirm(false)}
                          className="px-6 py-3 bg-gray-200 text-gray-800 rounded-lg font-semibold hover:bg-gray-300 transition-colors disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </form>

                {result && result.success && (
                  <div className="mt-6 bg-green-50 border border-green-200 rounded-lg p-4">
                    <p className="text-green-800 font-semibold mb-2">
                      ✅ User deleted successfully
                    </p>
                    <p className="text-sm text-green-700">
                      User ID <span className="font-mono">{result.user_id}</span> was
                      purged at {result.timestamp}.
                    </p>
                    {result.deleted && (
                      <details className="mt-3">
                        <summary className="text-sm text-green-700 cursor-pointer">
                          View deletion summary
                        </summary>
                        <pre className="mt-2 text-xs bg-white p-3 rounded-lg overflow-auto">
                          {JSON.stringify(result.deleted, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                )}

                {error && (
                  <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4">
                    <p className="text-red-800 font-semibold">Error</p>
                    <p className="text-sm text-red-700 mt-1">{error}</p>
                  </div>
                )}
              </section>

              <section>
                <h2 className="text-2xl font-semibold text-gray-900 mb-3">
                  Need assistance?
                </h2>
                <p>
                  For audit requests or complex data removal scenarios, reach out to{" "}
                  <a
                    href="mailto:support@smartcoach.app"
                    className="text-blue-600 hover:underline font-medium"
                  >
                    support@smartcoach.app
                  </a>
                  .
                </p>
              </section>
            </div>
          )}
        </div>
      </div>
    </AuthGuard>
  );
};

export default DataDeletion;
