// app/static/js/components/StatusAlert.js
const StatusAlert = {
  render(props) {
      const variants = {
          success: {
              icon: '✓',
              className: 'status-alert-success'
          },
          error: {
              icon: '✕',
              className: 'status-alert-error'
          },
          processing: {
              icon: '↻',
              className: 'status-alert-processing'
          }
      };

      const variant = variants[props.status] || variants.info;

      return React.createElement('div', {
          className: `status-alert ${variant.className}`,
          role: 'alert'
      }, [
          React.createElement('span', {
              className: 'status-alert-icon',
              key: 'icon'
          }, variant.icon),
          React.createElement('span', {
              className: 'status-alert-message',
              key: 'message'
          }, props.message)
      ]);
  }
};

export default StatusAlert;