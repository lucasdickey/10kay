#!/usr/bin/env python3
"""
Real-time monitor for orchestrator execution with phase overlap visualization
"""
import psycopg2
import time
from datetime import datetime
from pipeline.utils import get_config

def get_status():
    config = get_config()
    conn = psycopg2.connect(config.database.url)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM content WHERE filing_id = filings.id)) as analyzed,
            COUNT(*) FILTER (WHERE filings.status = 'pending' AND NOT EXISTS (SELECT 1 FROM content WHERE filing_id = filings.id)) as pending
        FROM filings
        JOIN companies c ON filings.company_id = c.id
        WHERE c.enabled = true
    """)
    result = cursor.fetchone()
    total_filings, analyzed, pending = result[0], result[1], result[2]
    analyze_pct = round(100.0 * analyzed / total_filings, 1) if total_filings > 0 else 0
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_content,
            COUNT(*) FILTER (WHERE blog_html IS NOT NULL) as with_blog_html
        FROM content
    """)
    result = cursor.fetchone()
    total_content, blog_html = result[0], result[1]
    gen_pct = round(100.0 * blog_html / total_content, 1) if total_content > 0 else 0
    
    cursor.close()
    conn.close()
    
    return {
        'total_filings': total_filings,
        'analyzed': analyzed,
        'pending': pending,
        'analyze_pct': analyze_pct,
        'total_content': total_content,
        'blog_html': blog_html,
        'gen_pct': gen_pct
    }

def draw_progress_bar(pct, width=40):
    filled = int(width * pct / 100)
    bar = '█' * filled + '░' * (width - filled)
    return f"{bar} {pct}%"

def main():
    print("\n" + "="*80)
    print("LEVEL 2 PARALLELIZATION - REAL-TIME MONITOR")
    print("="*80)
    print("\nPhase Overlap Strategy: Analyze (5 workers) + Generate (3 workers) in parallel")
    print("Expected Total Time: ~45-50 minutes vs ~90 min sequential\n")
    
    last_status = None
    iteration = 0
    
    while True:
        iteration += 1
        status = get_status()
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Check if something changed or it's time to print
        if status != last_status or iteration % 5 == 0:
            print(f"\n[{timestamp}] Status Update #{iteration}")
            print("-" * 80)
            
            # Analyze phase
            print(f"📊 PHASE 2: ANALYZE (5 workers)")
            print(f"   Progress: {status['analyzed']}/{status['total_filings']} filings")
            print(f"   {draw_progress_bar(status['analyze_pct'])}")
            print(f"   Remaining: {status['pending']} filings")
            
            # Generate phase
            print(f"\n📊 PHASE 3: GENERATE (3 workers) - Running in Parallel! ✓")
            print(f"   Progress: {status['blog_html']}/{status['total_content']} items")
            print(f"   {draw_progress_bar(status['gen_pct'])}")
            
            # Calculate estimated time
            if status['pending'] > 0:
                print(f"\n⏱️  ETA: Analyze completes in ~{max(1, status['pending'] // 11)} minutes")
            else:
                print(f"\n✅ Analyze phase COMPLETE!")
            
            last_status = status
        
        # Check if both phases complete
        if status['analyze_pct'] == 100.0 and status['gen_pct'] == 100.0:
            print("\n" + "="*80)
            print("✓ BOTH PHASES COMPLETE!")
            print("="*80)
            print(f"  Analyzed: {status['analyzed']}/{status['total_filings']} filings")
            print(f"  Generated: {status['blog_html']}/{status['total_content']} items")
            print(f"  Publish phase should now be running...")
            print("="*80 + "\n")
            break
        
        time.sleep(10)  # Check every 10 seconds

if __name__ == '__main__':
    main()
