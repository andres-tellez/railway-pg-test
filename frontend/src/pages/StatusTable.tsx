import React from "react";

function StatusRow({
  label,
  status,
  actionText,
  onAction,
}: {
  label: string;
  status: boolean;
  actionText?: string;
  onAction?: () => void;
}) {
  return (
    <tr className="border-b">
      <td className="py-2 px-4 font-medium">{label}</td>
      <td className="py-2 px-4">
        {status
          ? <span className="text-green-600 font-semibold">✅ Yes</span>
          : <span className="text-red-500 font-semibold">❌ No</span>
        }
      </td>
      <td className="py-2 px-4">
        {!status && onAction && (
          <button
            onClick={onAction}
            className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
          >
            {actionText}
          </button>
        )}
      </td>
    </tr>
  );
}

export default function StatusTable({
  status,
  actions,
}: {
  status: {
    authenticated: boolean;
    hasOnboarded: boolean;
    hasStrava: boolean;
    hasActivities: boolean;
  };
  actions: {
    onboard: () => void;
    connectStrava: () => void;
    fetchActivities: () => void;
  };
}) {
  return (
    <div className="bg-white shadow rounded-lg overflow-auto max-w-full">
      <table className="w-full table-auto">
        <thead>
          <tr className="bg-gray-100">
            <th className="py-2 px-4 text-left">Feature</th>
            <th className="py-2 px-4 text-left">Status</th>
            <th className="py-2 px-4 text-left">Action</th>
          </tr>
        </thead>
        <tbody>
          <StatusRow label="Authenticated" status={status.authenticated} />
          <StatusRow
            label="Onboarding Complete"
            status={status.hasOnboarded}
            actionText="Complete Onboarding"
            onAction={actions.onboard}
          />
          <StatusRow
            label="Strava Connected"
            status={status.hasStrava}
            actionText="Connect Strava"
            onAction={actions.connectStrava}
          />
          <StatusRow
            label="10+ Activities"
            status={status.hasActivities}
            actionText="Fetch Activities"
            onAction={actions.fetchActivities}
          />
        </tbody>
      </table>
    </div>
  );
}
