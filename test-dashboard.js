// Test script to simulate dashboard API calls
const https = require('http');

console.log('Testing dashboard API endpoints...\n');

// Test flight data endpoint
console.log('1. Testing /api/flight-data...');
const req1 = https.request({
    hostname: 'localhost',
    port: 8000,
    path: '/api/flight-data',
    method: 'GET'
}, (res) => {
    console.log(`Status: ${res.statusCode}`);
    console.log(`Headers: ${JSON.stringify(res.headers, null, 2)}`);
    
    let data = '';
    res.on('data', (chunk) => {
        data += chunk;
    });
    
    res.on('end', () => {
        try {
            const result = JSON.parse(data);
            console.log('✅ Flight data API response:');
            console.log('  Success:', result.success);
            console.log('  Has metadata:', !!result.metadata);
            console.log('  Has data:', !!result.data);
            console.log('  States count:', result.data?.states?.length || 0);
            console.log('  Response size:', data.length, 'bytes');
        } catch (e) {
            console.log('❌ JSON parse error:', e.message);
            console.log('First 200 chars:', data.substring(0, 200));
        }
        
        // Test stats endpoint
        console.log('\n2. Testing /api/latest-stats...');
        const req2 = https.request({
            hostname: 'localhost',
            port: 8000,
            path: '/api/latest-stats',
            method: 'GET'
        }, (res2) => {
            console.log(`Status: ${res2.statusCode}`);
            
            let data2 = '';
            res2.on('data', (chunk) => {
                data2 += chunk;
            });
            
            res2.on('end', () => {
                try {
                    const result2 = JSON.parse(data2);
                    console.log('✅ Stats API response:');
                    console.log('  Success:', result2.success);
                    console.log('  Has data:', !!result2.data);
                    console.log('  Total flights:', result2.data?.total_flights || 0);
                    console.log('  Response size:', data2.length, 'bytes');
                } catch (e) {
                    console.log('❌ JSON parse error:', e.message);
                }
                
                console.log('\n✅ Both API endpoints tested successfully');
            });
        });
        
        req2.on('error', (e) => {
            console.error('❌ Stats API request error:', e.message);
        });
        
        req2.end();
    });
});

req1.on('error', (e) => {
    console.error('❌ Flight data API request error:', e.message);
});

req1.setTimeout(30000, () => {
    console.log('❌ Request timeout (30s)');
    req1.destroy();
});

req1.end();