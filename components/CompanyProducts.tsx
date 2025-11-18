/**
 * CompanyProducts Component
 *
 * Displays detailed information about company products including:
 * - Product description
 * - Pricing model
 * - Marketing approach
 * - Direct and indirect customers
 * - Use cases and problems solved
 */

import { CompanyProduct } from '@/lib/company-types';

interface CompanyProductsProps {
  products?: CompanyProduct[] | null;
}

export function CompanyProducts({ products }: CompanyProductsProps) {
  // Don't render if no products
  if (!products || products.length === 0) {
    return null;
  }

  return (
    <div className="bg-white border rounded-lg p-6 shadow-sm">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Products & Services</h2>

      <div className="space-y-6">
        {products.map((product, index) => (
          <div
            key={index}
            className="border-l-4 border-blue-500 bg-gray-50 rounded-r-lg p-5"
          >
            {/* Product Name */}
            <h3 className="text-lg font-bold text-gray-900 mb-2">{product.name}</h3>

            {/* Product Description */}
            <p className="text-gray-700 mb-4 leading-relaxed">{product.description}</p>

            {/* Product Details Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              {/* Pricing Model */}
              {product.pricing && (
                <div>
                  <div className="text-xs font-semibold text-gray-500 mb-1 uppercase tracking-wide">
                    Pricing Model
                  </div>
                  <div className="text-sm text-gray-900">{product.pricing}</div>
                </div>
              )}

              {/* Marketing Approach */}
              {product.marketing && (
                <div>
                  <div className="text-xs font-semibold text-gray-500 mb-1 uppercase tracking-wide">
                    Marketing Approach
                  </div>
                  <div className="text-sm text-gray-900">{product.marketing}</div>
                </div>
              )}
            </div>

            {/* Customer Information */}
            {product.customers && (
              <div className="bg-white rounded-lg p-4 border border-gray-200">
                <h4 className="text-sm font-semibold text-gray-900 mb-3">Customer Segments</h4>

                <div className="space-y-3">
                  {/* Direct Customers */}
                  {product.customers.direct && product.customers.direct.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-green-600 mb-2 uppercase tracking-wide">
                        Direct Customers
                      </div>
                      <ul className="space-y-1">
                        {product.customers.direct.map((customer, idx) => (
                          <li key={idx} className="text-sm text-gray-700 flex items-start gap-2">
                            <span className="text-green-600 mt-1">•</span>
                            <span>{customer}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Indirect Customers */}
                  {product.customers.indirect && product.customers.indirect.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-blue-600 mb-2 uppercase tracking-wide">
                        Indirect/End Customers
                      </div>
                      <ul className="space-y-1">
                        {product.customers.indirect.map((customer, idx) => (
                          <li key={idx} className="text-sm text-gray-700 flex items-start gap-2">
                            <span className="text-blue-600 mt-1">•</span>
                            <span>{customer}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Use Cases / Problems Solved */}
                  {product.customers.use_cases && product.customers.use_cases.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-purple-600 mb-2 uppercase tracking-wide">
                        Problems Solved / Use Cases
                      </div>
                      <ul className="space-y-1">
                        {product.customers.use_cases.map((useCase, idx) => (
                          <li key={idx} className="text-sm text-gray-700 flex items-start gap-2">
                            <span className="text-purple-600 mt-1">✓</span>
                            <span>{useCase}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Product Count Summary */}
      {products.length > 1 && (
        <div className="mt-6 pt-4 border-t border-gray-200">
          <p className="text-sm text-gray-600 text-center">
            Total: <span className="font-semibold">{products.length}</span> product{products.length !== 1 ? 's' : ''} & service{products.length !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </div>
  );
}
