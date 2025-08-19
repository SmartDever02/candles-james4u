module.exports = {
    apps: [{
        name: 'miner3110',
        script: './miner_skx1_miner3110', // Update this to your miner script
        interpreter: '/bin/bash',
        cwd: '/root/candles',
        instances: 1,
        autorestart: true,
        watch: false,
        max_memory_restart: '1G',
        env: {
            NODE_ENV: 'production'
        },
        log_file: './logs/miner.log',
        out_file: './logs/miner-out.log',
        error_file: './logs/miner-error.log',
        time: true,
        merge_logs: true
    }]
};
