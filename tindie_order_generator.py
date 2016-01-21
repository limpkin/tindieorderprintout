from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import Encoders
from datetime import datetime, date, time
import requests
import smtplib
import time
import fpdf
import sys

debug = True
username =             
auth_token =           
email =                
email_password =       
email_smtp =           
manufacturer_email =   
manufacturer_name =    

def send_tindie_request(filters):
	# Request params
	params = {"username":username, "api_key":auth_token, "format":"json"}
	# Append filters
	for item in filters:
		params[item] = filters[item]
	
	# Send request
	r = requests.get("https://www.tindie.com/api/v1/order", params);
	if r.status_code != requests.codes.ok :
		print "Wrong return status code!"
		print "Status code:", r.status_code
		print "Request URL:",  r.url
		print "Return text:",  r.text
		sys.exit()
	else:
		return r.json()
		
		
def query_tindie_orders(filters):
	# Send first request
	query_result = send_tindie_request(filters)
	query_total_nb = query_result["meta"]["total_count"]
	return_data = query_result["orders"]
	
	# Debug info
	if debug:
		print "Number elements in sent query result:", len(query_result["orders"])
		print "Total number of elements for query:", query_total_nb
		print "Number of elements fetched so far:", len(return_data)
			
	# Send other requests if we need to
	while len(return_data) < query_total_nb:
		# Update offset and send query
		filters["offset"] = str(len(return_data))
		query_result = send_tindie_request(filters)
		return_data.extend(query_result["orders"])
		# Debug info
		if debug:
			print "Number elements in sent query result:", len(query_result["orders"])
			print "Total number of elements for query:", query_total_nb
			print "Number of elements fetched so far:", len(return_data)
	
	# Return matching orders
	return return_data
	
def generate_pdf_for_order(order):
	###################
	# DATA EXTRACTION #
	###################
	#name
	order_name = "Tindie Order #" + str(order["number"])
	# date, from 2016-01-20T21:34:40.668727 to Wednesday, 20. January 2016 09:34PM
	head, sep, tail = order["date"].partition('T')
	item_date = head.split('-')
	head, sep, tail = tail.partition('.')
	item_time =  head.split(':')
	order_date = datetime(int(item_date[0]), int(item_date[1]), int(item_date[2]), int(item_time[0]), int(item_time[1]), int(item_time[2]))
	order_date =  order_date.strftime("%A, %d. %B %Y %I:%M%p")
	
	##################
	# PDF GENERATION #
	##################
	# Load PDF template
	pdf = fpdf.Template(format="A4", title=order_name)
	pdf.parse_csv("template.csv", delimiter=";", decimal_sep=",")
	pdf.add_page()
	# Fill the correct fields	
	pdf["top1_1logo"] = "tindie_logo.png";
	pdf["top1_2ordernumber"] = order_name;
	pdf["top1_3date"] = order_date;
	pdf["ship2_2name"] = str(order["shipping_name"]);
	pdf["ship2_3address"] = str(order["shipping_street"]);
	pdf["ship2_4citystate"] = str(order["shipping_city"]) + ", " + str(order["shipping_state"])
	pdf["ship2_5postcode"] = str(order["shipping_postcode"])
	pdf["ship2_6country"] = str(order["shipping_country"])
	pdf["ship2_7phone"] = str(order["phone"])
	pdf["ship1_method"] = str(order["shipping_service"])
	if str(order["shipping_instructions"]) != "":
		pdf["ship1_notes"] = "Delivery Instructions: " + str(order["shipping_instructions"])
	else:
		pdf["ship1_notes"] = "Delivery Instructions: none"
		
	# Middle table: product, quantity, price, total
	order_items = order["items"]
	for i in range(0, len(order_items)):
		#for data in order_items[i]:
		#	print data, order_items[i][data]
		# item name
		item_printout = order_items[i]["product"]
		item_printout = item_printout.replace("Mooltipass Offline Password Keeper", "Mooltipass ")
		item_printout = item_printout.replace("The Whistled - A Whistle Detection Device", "Whistled ")
		if order_items[i]["options"] is not None:
			order_items[i]["options"] = order_items[i]["options"].replace("Case material: ", "")
			order_items[i]["options"] = order_items[i]["options"].replace("Laser Cut Holder: ", "")
			order_items[i]["options"] = order_items[i]["options"].replace("Extra Cards: ", "")
			order_items[i]["options"] = order_items[i]["options"].replace("AC/DC and LED strip: ", "")
			item_printout += order_items[i]["options"]
		pdf["mid"+str(i+1)+"_1prod"] = item_printout
		pdf["mid"+str(i+1)+"_2quant"] = str(order_items[i]["quantity"])
		pdf["mid"+str(i+1)+"_3unit"] = "$"+str(order_items[i]["price_unit"])
		pdf["mid"+str(i+1)+"_4tot"] = "$"+str(order_items[i]["price_total"]	)	
	
	# Bottom table: shipping, discount, total
	pdf["bot1_shipping"] = "$" + str(order["total_shipping"])
	pdf["bot2_discount"] = "$" + str(order["total_discount"])
	pdf["bot3_total"] = "$" + str(order["total_subtotal"])
	
	# PDF generation
	pdf_name = order_name + ".pdf"
	pdf.render(pdf_name)
	return pdf_name


if __name__ == '__main__':	
	# Main program
	print "Tindie Orders Generator\n"
	
	# local vars
	file_names = [];
	order_printouts = [];
		
	# Request non shipped orders
	orders = query_tindie_orders({"shipped":"false"})
	# Loop through them
	for tindie_order in orders:
		# Tindie bug...
		if tindie_order["shipping_street"] != "Unavailable until we have finished billing the customer":
			print ""
			print "New order for", tindie_order["shipping_name"]
			#for items in tindie_order:
			#	print items, ":", tindie_order[items]
			# Loop through the order items
			item_printout = "- #" + str(tindie_order["number"]) + ": "
			order_valid = True
			for item in tindie_order["items"]:
				item_printout += str(item["quantity"]) + "x " + item["product"]
				if item["options"] is not None:
					item_printout += item["options"]
				# Check that it is billed
				if item["status"] != "billed":
					order_valid = False
					print "Item not billed!!!!"
				item_printout += ", "
			
			# Format printout
			item_printout = item_printout[:-2]
			if tindie_order["shipping_service"].find("DHL") >= 0:
				item_printout += " - DHL SHIPPING !"
			
			# Check that the order is valid
			print item_printout
			if order_valid:				
				# Generate PDF
				file_names.append(generate_pdf_for_order(tindie_order))
				order_printouts.append(item_printout)
				
	# if we actually have orders today!
	if len(order_printouts) > 0:
		# prepare email text
		email_text = "Hello " + manufacturer_name + ",<br><br>"
		email_text += "Here are the new orders for today:<br>"
		for item in order_printouts:
			email_text += item + "<br>"
		email_text += "<br>Thanks a lot!"
		
		# prepare and send email
		msg = MIMEMultipart()
		msg['Subject'] = "New Orders For Today" 
		msg['From'] = email
		msg['To'] = manufacturer_email + "," + email
		msg.attach(MIMEText(email_text, 'html'))

		for f in file_names:
			part = MIMEBase('application', "octet-stream")
			part.set_payload(open(f,"rb").read())
			Encoders.encode_base64(part)
			part.add_header('Content-Disposition', 'attachment; filename=\"'+f+"\"")
			msg.attach(part)

		smtp = smtplib.SMTP(email_smtp, 587)
		smtp.ehlo()
		smtp.starttls()
		smtp.login(email, email_password)
		smtp.sendmail(email, manufacturer_email, msg.as_string())
		smtp.quit()			
	
	raw_input("Email sent! Press enter")
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	