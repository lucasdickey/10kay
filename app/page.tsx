export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8">
      <main className="max-w-4xl mx-auto text-center">
        <h1 className="text-6xl font-bold mb-4">
          10KAY
        </h1>
        <p className="text-xl text-gray-600 dark:text-gray-400 mb-8">
          SEC Filing Analysis for Tech Companies
        </p>

        <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-8 text-left">
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-gray-700 dark:text-gray-300 mb-4">
            Automated analysis and insights from 10-K and 10-Q filings, delivered daily.
          </p>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-green-500">✓</span>
              <span>AWS Infrastructure Ready</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-green-500">✓</span>
              <span>Next.js Application Initialized</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-yellow-500">○</span>
              <span>Content Processing Pipeline - In Progress</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-400">○</span>
              <span>User Authentication - Pending</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-400">○</span>
              <span>Email Newsletter - Pending</span>
            </div>
          </div>
        </div>

        <p className="mt-8 text-sm text-gray-500">
          Tracking {47} tech companies across NASDAQ and NYSE
        </p>
      </main>
    </div>
  );
}
